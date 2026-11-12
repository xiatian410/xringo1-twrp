#include <android/binder_ibinder.h>
#include <android/binder_manager.h>
#include <chrono>
#include <cstdio>
#include <thread>

// checkService never asks init to lazily launch an unselected HAL. The caller
// also applies an external deadline in case the Binder driver itself stalls.
int main() {
    static constexpr const char* names[] = {
        "android.hardware.security.keymint.IKeyMintDevice/default",
        "android.hardware.gatekeeper.IGatekeeper/default",
        "android.hardware.security.sharedsecret.ISharedSecret/default",
        "android.hardware.security.secureclock.ISecureClock/default",
        "android.system.keystore2.IKeystoreService/default",
    };
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(15);
    do {
        bool ready = true;
        for (const char* name : names) {
            AIBinder* service = AServiceManager_checkService(name);
            if (!service) {
                ready = false;
                continue;
            }
            if (AIBinder_ping(service) != STATUS_OK) ready = false;
            AIBinder_decStrong(service);
        }
        if (ready) {
            std::puts("MiTEE and keystore interfaces registered and responding");
            return 0;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    } while (std::chrono::steady_clock::now() < deadline);
    std::fputs("MiTEE/keystore readiness deadline exceeded\n", stderr);
    return 1;
}
