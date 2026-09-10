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

static constexpr const char *NETPLAY_COMMAND = "/tmp/diablo-netplay.command";
static std::string last_netplay_command;

static void write_netplay_command()
{
    const uint32_t action = user_io_status_get("[8:7]");
    const char *mode = action == 1 ? "host" : action == 2 ? "join" : "off";
    static constexpr const char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    std::string code;
    bool complete = action == 1 || action == 2;
    const char *fields[] = {"[14:10]", "[19:15]", "[24:20]", "[29:25]", "[34:30]"};
    for (const char *field : fields) {
        const uint32_t value = user_io_status_get(field);
        if (value == 0 || value > 26) {
            complete = false;
            code.push_back('_');
        } else {
            code.push_back(alphabet[value - 1]);
        }
    }
    if (!complete) mode = "off";

    std::string command = std::string("schema=diablo-netplay-v1\nmode=") + mode +
        "\ncode=" + code + "\n";
    if (command == last_netplay_command) return;

    const std::string temporary = std::string(NETPLAY_COMMAND) + ".tmp";
    int descriptor = open(temporary.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    if (descriptor < 0) return;
    const ssize_t written = write(descriptor, command.data(), command.size());
    if (written == static_cast<ssize_t>(command.size())) fsync(descriptor);
    close(descriptor);
    if (written == static_cast<ssize_t>(command.size()) && rename(temporary.c_str(), NETPLAY_COMMAND) == 0)
        last_netplay_command = command;
    else
        unlink(temporary.c_str());
}

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
        const_cast<char *>("--save-root"), const_cast<char *>("/media/fat/games/Diablo/Saves"),
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
    // Netplay is opt-in per boot. Code fields may be retained by MiSTer's
    // status configuration, but a stale HOST/JOIN action must never relaunch
    // a network session without an explicit selection in this boot.
    user_io_status_set("[8:7]", 0);
    unlink(NETPLAY_COMMAND);
    unlink("/tmp/diablo-netplay.command.tmp");
    write_netplay_command();
    release_core_reset();
    sleep(1);
    launch_runtime(rbf_path);

    while (true) {
        if (!is_fpga_ready(1)) {
            stop_runtime();
            fpga_wait_to_reset();
        }
        if (runtime_pid > 0 && waitpid(runtime_pid, nullptr, WNOHANG) == runtime_pid)
            runtime_pid = -1;
        user_io_poll();
        frame_timer();
        input_poll(0);
        HandleUI();
        OsdUpdate();
        write_netplay_command();
    }
}
