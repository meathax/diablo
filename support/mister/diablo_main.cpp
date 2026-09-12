// SPDX-License-Identifier: GPL-3.0-only
// Resident MiSTer-Main derivative for the Diablo RBF handoff.
// Selected by MiSTer.ini's [Diablo] main=Diablo entry after either visible
// Diablo RBF is selected from _Other.  The process remains the normal HPS
// I/O/OSD owner while its child starts the packaged DevilutionX runtime.
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <fcntl.h>
#include <sched.h>
#include <signal.h>
#include <sys/stat.h>

#include "menu.h"
#include "user_io.h"
#include "input.h"
#include "frame_timer.h"
#include "fpga_io.h"
#include "osd.h"
#include "offload.h"

const char *version = "$VER:" VDATE;

static pid_t runtime_pid = -1;


static bool hellfire_selected(const char *rbf_path)
{
    std::string name = rbf_path ? rbf_path : "";
    for (char &character : name)
        if (character >= 'A' && character <= 'Z') character += 'a' - 'A';
    return name.find("hellfire") != std::string::npos;
}

// app_restart() holds the core in reset immediately before exec'ing this
// main= handler.  Release it using the standard Main_MiSTer GPO sequence.
static void release_core_reset()
{
    constexpr off_t manager = 0xFF706000u;
    constexpr size_t size = 0x1000u;
    constexpr size_t gpo_offset = 0x10u;
    int descriptor = open("/dev/mem", O_RDWR | O_SYNC | O_CLOEXEC);
    if (descriptor < 0) return;
    void *mapping = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_SHARED, descriptor, manager);
    close(descriptor);
    if (mapping == MAP_FAILED) return;
    volatile uint32_t *gpo = static_cast<volatile uint32_t *>(mapping) + (gpo_offset / sizeof(uint32_t));
    const uint32_t original = *gpo;
    *gpo = original & ~0xC0000000u;
    usleep(1000);
    *gpo = (original & ~0xC0000000u) | 0x80000000u;
    munmap(mapping, size);
}

static void launch_runtime(const char *rbf_path)
{
    const char *campaign = hellfire_selected(rbf_path) ? "hellfire" : "diablo";
    runtime_pid = fork();
    if (runtime_pid < 0) {
        runtime_pid = -1;
        return;
    }
    if (runtime_pid != 0) {
        setpgid(runtime_pid, runtime_pid);
        return;
    }

    // Keep the Python supervisor and its DevilutionX child in a dedicated
    // group.  A newly selected core then tears down the entire game session,
    // rather than leaving an orphan process attached to stale DDR transport.
    setpgid(0, 0);
    prctl(PR_SET_PDEATHSIG, SIGKILL);
    char *const command[] = {
        const_cast<char *>("/usr/bin/python3"),
        const_cast<char *>("/media/fat/_Other/Diablo/diablo_launcher.py"),
        const_cast<char *>("--package-root"), const_cast<char *>("/media/fat/_Other/Diablo"),
        const_cast<char *>("--data-root"), const_cast<char *>("/media/fat/games/Diablo"),
        const_cast<char *>("--save-root"), const_cast<char *>("/media/fat/saves/Diablo"),
        const_cast<char *>("--campaign"), const_cast<char *>(campaign),
        const_cast<char *>("--core-already-loaded"), nullptr
    };
    execv(command[0], command);
    _exit(127);
}

static void stop_runtime()
{
    if (runtime_pid <= 0) return;
    kill(-runtime_pid, SIGTERM);
    for (int attempt = 0; attempt < 200; ++attempt) {
        if (waitpid(runtime_pid, nullptr, WNOHANG) == runtime_pid) {
            runtime_pid = -1;
            return;
        }
        usleep(50000);
    }
    kill(-runtime_pid, SIGKILL);
    while (waitpid(runtime_pid, nullptr, 0) < 0 && errno == EINTR) {}
    runtime_pid = -1;
}

static void return_to_mister_menu()
{
    // A clean DevilutionX exit must not leave this resident main= handler
    // holding the video path with its OSD disabled.  Restart through the stock
    // MiSTer executable so menu.rbf is loaded and the normal menu is restored.
    app_restart("menu.rbf", nullptr, "/media/fat/MiSTer");
    _exit(EXIT_FAILURE);
}

int main(int argc, char *argv[])
{
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(1, &set);
    sched_setaffinity(0, sizeof(set), &set);

    const char *rbf_path = argc > 1 ? argv[1] : "/media/fat/_Other/Diablo.rbf";
    offload_start();
    fpga_io_init();
    fpga_set_transition_hook(stop_runtime);
    DISKLED_OFF;
    if (!is_fpga_ready(1)) return EXIT_FAILURE;

    FindStorage();
    user_io_init(rbf_path, argc > 2 ? argv[2] : nullptr);
    // The MiSTer core selector can leave its OSD surface active while this
    // main= handler starts. Close it before releasing reset so boot presents
    // only the core's blank video until the runtime publishes its first frame.
    OsdDisable();
    release_core_reset();
    // The reset sequence already includes the hardware pulse delay.  Keep a
    // short settle window for the resident core, without holding the screen
    // blank for a full second before starting package verification.
    usleep(100000);
    launch_runtime(rbf_path);

    while (true) {
        if (!is_fpga_ready(1)) {
            stop_runtime();
            fpga_wait_to_reset();
        }
        if (runtime_pid > 0 && waitpid(runtime_pid, nullptr, WNOHANG) == runtime_pid) {
            runtime_pid = -1;
            return_to_mister_menu();
        }
        user_io_poll();
        frame_timer();
        input_poll(0);
        HandleUI();
        OsdUpdate();
    }
}
