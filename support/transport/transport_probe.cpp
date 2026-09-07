// SPDX-License-Identifier: GPL-2.0-or-later
// Minimal target-side preflight for the MiSTer shared-DDR transport aperture.
#include "mister_transport_admission.hpp"
#include "mister_transport_runtime.hpp"

#include <cerrno>
#include <chrono>
#include <cinttypes>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <fcntl.h>
#include <limits>
#include <sys/mman.h>
#include <thread>
#include <unistd.h>

namespace {
using diablo::mister::transport::ParsePhysicalAperture;
using diablo::mister::transport::TransportLease;
using diablo::mister::transport::TransportRuntime;

constexpr size_t kReservationBytes = 2 * 1024 * 1024;
constexpr uint64_t kArmChallenge = UINT64_C(0xD1AB10F0C0DEC0DE);
constexpr uint64_t kFpgaAck = UINT64_C(0xF9A0BEEFC0DEC0DE);

int fail(const char *message)
{
    std::fprintf(stderr, "transport-probe: %s: %s\n", message, std::strerror(errno));
    return 1;
}

int selfTest()
{
    auto aperture = ParsePhysicalAperture("0x3FE00000", kReservationBytes, 4096,
                                          std::numeric_limits<uint64_t>::max());
    if (!aperture.has_value() || aperture->page_base != UINT64_C(0x3FE00000)
        || aperture->mapped_bytes != kReservationBytes) {
        std::fputs("transport-probe: invalid reservation size\n", stderr);
        return 1;
    }
    std::puts("transport-probe self-test: passed");
    return 0;
}
} // namespace

int main(int argc, char **argv)
{
    if (argc == 2 && std::strcmp(argv[1], "--self-test") == 0) return selfTest();
    if (argc != 1) {
        std::fprintf(stderr, "usage: %s [--self-test]\n", argv[0]);
        return 2;
    }

    const char *physical = std::getenv("DIABLO_MISTER_SHARED_PHYS");
    const long page_size = sysconf(_SC_PAGESIZE);
    if (physical == nullptr || *physical == '\0' || page_size <= 0) {
        std::fputs("transport-probe: current physical admission is required\n", stderr);
        return 1;
    }
    auto aperture = ParsePhysicalAperture(
        physical, kReservationBytes, static_cast<uint64_t>(page_size),
        static_cast<uint64_t>(std::numeric_limits<off_t>::max()));
    if (!aperture.has_value() || !TransportRuntime::HasCurrentBootAdmission(*aperture)) {
        std::fputs("transport-probe: physical aperture does not match current boot admission\n", stderr);
        return 1;
    }
    auto lease = TransportLease::Acquire();
    if (!lease.has_value()) {
        std::fputs("transport-probe: another transport writer owns the aperture\n", stderr);
        return 1;
    }

    const int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) return fail("open /dev/mem");
    void *mapping = mmap(nullptr, aperture->mapped_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd,
                         static_cast<off_t>(aperture->page_base));
    if (mapping == MAP_FAILED) {
        const int result = fail("map shared-DDR reservation");
        close(fd);
        return result;
    }

    auto *const words = reinterpret_cast<volatile uint64_t *>(
        static_cast<std::byte *>(mapping) + aperture->page_offset);
    const uint64_t initial_challenge = words[0];
    const uint64_t initial_ack = words[1];
    words[1] = 0;
    words[0] = kArmChallenge;
    __sync_synchronize();
    const uint64_t written_challenge = words[0];
    const uint64_t written_ack = words[1];
    std::fprintf(stderr, "transport-probe: initial=[0x%016" PRIx64 ",0x%016" PRIx64
                         "] after-write=[0x%016" PRIx64 ",0x%016" PRIx64 "]\n",
                 initial_challenge, initial_ack, written_challenge, written_ack);
    errno = 0;
    const int msync_result = msync(mapping, 4096, MS_SYNC);
    if (msync_result != 0 && errno != EINVAL) {
        const int result = fail("flush shared-DDR challenge");
        munmap(mapping, aperture->mapped_bytes);
        close(fd);
        return result;
    }
    if (msync_result != 0 && errno == EINVAL) {
        // /dev/mem O_SYNC mappings are device mappings on MiSTer. They have
        // no page-cache backing and therefore reject msync; the preceding
        // ARM barrier orders the volatile stores before FPGA observation.
        std::fputs("transport-probe: O_SYNC device mapping has no msync operation; using ARM barrier\n", stderr);
    }

    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(3);
    while (std::chrono::steady_clock::now() < deadline) {
        __sync_synchronize();
        if (words[1] == kFpgaAck) {
            std::printf("transport-probe: passed base=0x%08" PRIx64 " bytes=%zu ack=0x%016" PRIx64 "\n",
                        aperture->requested_base, kReservationBytes, words[1]);
            munmap(mapping, aperture->mapped_bytes);
            close(fd);
            return 0;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    std::fprintf(stderr, "transport-probe: FPGA acknowledgement timed out challenge=0x%016" PRIx64
                         " ack=0x%016" PRIx64 "\n", words[0], words[1]);
    munmap(mapping, aperture->mapped_bytes);
    close(fd);
    return 1;
}
