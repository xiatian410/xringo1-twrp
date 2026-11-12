// SPDX-License-Identifier: Apache-2.0
// One init exec serializes configuration changes. Properties express requests;
// sys.usb.state is published only after checked configfs operations/readback.
#include "usb_config.hpp"
#include <algorithm>
#include <cstdio>
#include <cctype>
#include <map>
#include <utility>
namespace dijun_usb {
static const std::string root = "/config/usb_gadget/g1";
static const std::string config = root + "/configs/b.1";
static std::string leaf(const std::string& s) { return s.substr(s.find_last_of('/') + 1); }
static bool set(Platform& p, const std::string& k, const std::string& v) {
    return p.get(k) == v || p.set(k, v);
}
static bool stopped(Platform& p, const std::string& s) {
    auto v = p.get("init.svc." + s);
    return v.empty() || v == "stopped";
}
static bool unbind(Platform& p) {
    if (!set(p, "sys.usb.state", "configuring")) return false;
    auto udc = p.read(root + "/UDC");
    if (!udc) return false;
    if (!udc->empty()) {
        // A newline is a nonempty write normalized to an empty controller name
        // by both upstream and Android configfs. Never issue a zero-byte write.
        if (!p.write(root + "/UDC", "\n")) return false;
        udc = p.read(root + "/UDC");
        if (!udc || !udc->empty()) return false;
    }
    auto links = p.links();
    if (!links) return false;
    for (const auto& name : *links) if (!p.remove(config + "/" + name)) return false;
    return true;
}
static int failure(Platform& p, const char* stage) {
    std::fprintf(stderr, "dijun USB configuration failed: %s\n", stage);
    unbind(p);
    set(p, "sys.usb.state", "error");
    set(p, "sys.recovery.usb.error", stage);
    return 1;
}
int reconcile(Platform& p) {
    const auto requested = p.get("sys.usb.config");
    if (requested != "none" && requested != "adb" && requested != "sideload" &&
        requested != "fastboot" && requested != "mtp" && requested != "mtp,adb")
        return failure(p, "unsupported-config");
    const auto controller = p.get("sys.usb.controller");
    if (controller != "e1ac0000.dwc3") return failure(p, "unknown-controller");
    const bool external = requested == "sideload";
    const std::string owner = external ? "minadbd" : requested == "fastboot" ? "fastbootd" :
        (requested == "adb" || requested == "mtp,adb") ? "adbd" : "none";
    const bool managed_service = owner == "adbd" || owner == "fastbootd";
    if (p.get("sys.recovery.usb.owner") != owner) {
        // recovery stops normal ADB via an acknowledged "none", then forks
        // minadbd before requesting sideload. Its ready may arrive first.
        if (external && (p.get("sys.recovery.usb.owner") != "none" ||
            !stopped(p, "adbd") || !stopped(p, "fastbootd"))) return failure(p, "sideload-owner-busy");
        if (!unbind(p) || (!external && !set(p, "sys.usb.ffs.ready", "0")) ||
            !set(p, "sys.recovery.usb.phase", "stopping") ||
            !set(p, "sys.recovery.usb.owner", owner)) return failure(p, "owner-change");
        // Stop both possible owners before reusing their shared ready property.
        // ctl messages are asynchronous; service-state triggers complete this phase.
        for (const auto& service : {"adbd", "fastbootd"})
            if (!stopped(p, service) && !p.set("ctl.stop", service)) return failure(p, "stop-service");
    }
    if (p.get("sys.recovery.usb.phase") == "stopping") {
        if (!stopped(p, "adbd") || !stopped(p, "fastbootd")) return 0;
        if (!set(p, "sys.recovery.usb.phase", managed_service ? "starting" : "ready"))
            return failure(p, "phase-update");
        if (managed_service && !p.set("ctl.start", owner)) return failure(p, "start-service");
    }
    if (managed_service && p.get("init.svc." + owner) != "running") {
        if (!unbind(p) || !set(p, "sys.usb.ffs.ready", "0")) return failure(p, "service-lost");
        // A starting phase already has a queued ctl.start; don't enqueue duplicates.
        if (stopped(p, owner) && p.get("sys.recovery.usb.phase") != "starting") {
            if (!set(p, "sys.recovery.usb.phase", "starting") || !p.set("ctl.start", owner))
                return failure(p, "restart-service");
        }
        return 0;
    }
    if (managed_service && p.get("init.svc." + owner) == "running")
        if (!set(p, "sys.recovery.usb.phase", "ready")) return failure(p, "phase-update");
    const bool ready = (external ? stopped(p, "adbd") && stopped(p, "fastbootd") :
                       managed_service && p.get("init.svc." + owner) == "running") &&
                       p.get("sys.usb.ffs.ready") == "1";
    const bool mtp = p.get("sys.usb.ffs.mtp.ready") == "1";
    std::string target = "none";
    if (requested == "mtp" && mtp) target = "mtp";
    if (ready) {
        if (requested == "mtp,adb") target = mtp ? "mtp,adb" : "adb";
        else if (requested == "adb" || requested == "sideload" || requested == "fastboot") target = requested;
    }
    // An MTP-only function may remain usable without ADB; combined mode waits
    // for ADB and temporarily exposes ADB alone while MTP is unavailable.
    auto stable = [&] {
        return p.get("sys.usb.config") == requested && p.get("sys.usb.controller") == controller &&
            (p.get("sys.usb.ffs.mtp.ready") == "1") == mtp &&
            (owner == "none" || ((external ? stopped(p, "adbd") && stopped(p, "fastbootd") :
                                 p.get("init.svc." + owner) == "running") &&
                                 (p.get("sys.usb.ffs.ready") == "1") == ready));
    };
    if (target == "none") {
        if (!unbind(p)) return failure(p, "unbind");
        // "none" acknowledges both the gadget detachment and service stop.
        // The sideload caller may fork minadbd as soon as it sees this value.
        if (requested == "none" && !set(p, "sys.usb.state", "none")) return failure(p, "publish-none");
        set(p, "sys.recovery.usb.error", "");
        return 0;
    }
    std::map<std::string,std::string> wanted;
    if (target == "mtp" || target == "mtp,adb") {
        wanted["f1"] = "ffs.mtp";
        if (target == "mtp,adb") wanted["f2"] = "ffs.adb";
    } else wanted["f1"] = target == "fastboot" ? "ffs.fastboot" : "ffs.adb";
    const bool has_mtp = target == "mtp" || target == "mtp,adb";
    auto hex_id = [](std::string value) -> std::optional<std::string> {
        if (value.starts_with("0x") || value.starts_with("0X")) value.erase(0, 2);
        if (value.empty() || value.size() > 4 || !std::all_of(value.begin(), value.end(),
            [](unsigned char c) { return std::isxdigit(c); })) return {};
        value.insert(0, 4 - value.size(), '0');
        std::transform(value.begin(), value.end(), value.begin(),
            [](unsigned char c) { return std::tolower(c); });
        return "0x" + value;
    };
    auto vid = hex_id(has_mtp ? "2717" : p.get("ro.recovery.usb.vid"));
    auto pid = hex_id(has_mtp ? (target == "mtp" ? "ff40" : "ff48") :
        p.get(target == "fastboot" ? "ro.recovery.usb.fastboot.pid" : "ro.recovery.usb.adb.pid"));
    if (!vid || !pid) return failure(p, "invalid-usb-id");
    const std::map<std::string,std::string> attributes = {
        {root + "/idVendor", *vid},
        {root + "/idProduct", *pid},
        {config + "/strings/0x409/configuration", target == "mtp,adb" ? "mtp_adb" : target == "sideload" ? "adb" : target},
        {root + "/os_desc/use", (target == "mtp" || target == "mtp,adb") ? "1" : "0"}
    };
    auto matches = [&] {
        auto names = p.links();
        if (!names || names->size() != wanted.size()) return false;
        for (const auto& [name, function] : wanted) {
            auto link = p.link(config + "/" + name);
            if (!link || leaf(*link) != function) return false;
        }
        for (const auto& [path, value] : attributes) {
            auto actual = p.read(path);
            if (!actual) return false;
            if (path.ends_with("/idVendor") || path.ends_with("/idProduct"))
                std::transform(actual->begin(), actual->end(), actual->begin(), [](unsigned char c) { return std::tolower(c); });
            if (*actual != value) return false;
        }
        return true;
    };
    auto udc = p.read(root + "/UDC");
    if (!udc) return failure(p, "read-controller");
    if (*udc != controller || !matches()) {
        if (!unbind(p)) return failure(p, "unbind");
        for (const auto& [path, value] : attributes)
            if (!p.write(path, value)) return failure(p, "write-attributes");
        for (const auto& [name, function] : wanted)
            if (!p.add(root + "/functions/" + function, config + "/" + name)) return failure(p, "link-function");
        if (!stable()) { if (!unbind(p)) return failure(p, "superseded"); return 0; }
        if (!matches() || !p.write(root + "/UDC", controller)) return failure(p, "bind");
    }
    udc = p.read(root + "/UDC");
    if (!udc || *udc != controller || !matches()) return failure(p, "bind-readback");
    if (!stable()) { if (!unbind(p)) return failure(p, "superseded"); return 0; }
    if (!set(p, "sys.usb.state", target)) return failure(p, "publish-state");
    set(p, "sys.recovery.usb.error", "");
    return 0;
}
}
#ifndef DIJUN_USB_CONFIG_TEST
#include <android-base/file.h>
#include <android-base/properties.h>
#include <android-base/strings.h>
#include <dirent.h>
#include <fcntl.h>
#include <limits.h>
#include <sys/stat.h>
#include <unistd.h>
namespace {
struct Device final : dijun_usb::Platform {
    std::string get(const std::string& k) override { return android::base::GetProperty(k, ""); }
    bool set(const std::string& k, const std::string& v) override { return android::base::SetProperty(k, v); }
    std::optional<std::string> read(const std::string& path) override {
        std::string out;
        if (!android::base::ReadFileToString(path, &out)) return {};
        return android::base::Trim(out);
    }
    bool write(const std::string& path, const std::string& value) override {
        int fd = TEMP_FAILURE_RETRY(open(path.c_str(), O_WRONLY | O_CLOEXEC));
        if (fd < 0) return false;
        auto n = TEMP_FAILURE_RETRY(::write(fd, value.data(), value.size()));
        int error = errno; int closed = close(fd); errno = error;
        return n == static_cast<ssize_t>(value.size()) && closed == 0;
    }
    std::optional<std::vector<std::string>> links() override {
        const std::string path = "/config/usb_gadget/g1/configs/b.1";
        DIR* dir = opendir(path.c_str()); if (!dir) return {};
        std::vector<std::string> out; errno = 0;
        while (auto* entry = readdir(dir)) {
            struct stat st{};
            if (fstatat(dirfd(dir), entry->d_name, &st, AT_SYMLINK_NOFOLLOW) != 0) { closedir(dir); return {}; }
            if (S_ISLNK(st.st_mode)) out.emplace_back(entry->d_name);
            errno = 0;
        }
        int error = errno; closedir(dir); if (error) return {}; return out;
    }
    std::optional<std::string> link(const std::string& path) override {
        char buf[PATH_MAX]; auto n = readlink(path.c_str(), buf, sizeof(buf));
        if (n < 0 || n == static_cast<ssize_t>(sizeof(buf))) return {}; return std::string(buf, n);
    }
    bool add(const std::string& target, const std::string& path) override { return symlink(target.c_str(), path.c_str()) == 0; }
    bool remove(const std::string& path) override { return unlink(path.c_str()) == 0 || errno == ENOENT; }
};
}
int main() { Device device; return dijun_usb::reconcile(device); }
#endif
