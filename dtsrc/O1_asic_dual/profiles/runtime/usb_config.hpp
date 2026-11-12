#pragma once
#include <optional>
#include <string>
#include <vector>
namespace dijun_usb {
// Boundary only: the state machine is shared by the init executable and host fixture.
struct Platform {
    virtual ~Platform() = default;
    virtual std::string get(const std::string&) = 0;
    virtual bool set(const std::string&, const std::string&) = 0;
    virtual std::optional<std::string> read(const std::string&) = 0;
    virtual bool write(const std::string&, const std::string&) = 0;
    virtual std::optional<std::vector<std::string>> links() = 0;
    virtual std::optional<std::string> link(const std::string&) = 0;
    virtual bool add(const std::string&, const std::string&) = 0;
    virtual bool remove(const std::string&) = 0;
};
int reconcile(Platform&);
}
