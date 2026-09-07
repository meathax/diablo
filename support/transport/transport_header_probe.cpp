// SPDX-License-Identifier: GPL-2.0-or-later
// Target-side ABI v1 control-page attachment probe for the MiSTer DDR aperture.
#include "transport_abi.hpp"

#include <array>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cinttypes>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <span>
#include <thread>
#include <vector>
#include <sys/mman.h>
#include <unistd.h>

namespace {
using diablo::mister::transport::AbiView;
using diablo::mister::transport::AttachError;
using diablo::mister::transport::ComponentState;
using diablo::mister::transport::FrameOffset;
using diablo::mister::transport::FrameState;
using diablo::mister::transport::Header;
using diablo::mister::transport::PaletteOffset;
using diablo::mister::transport::FRAME_HEIGHT;
using diablo::mister::transport::FRAME_PIXEL_BYTES;
using diablo::mister::transport::FRAME_WIDTH;
using diablo::mister::transport::FRAME_CHECKSUM_ABSENT;
using diablo::mister::transport::INPUT_CAPACITY;
using diablo::mister::transport::INPUT_RECORD_BYTES;
using diablo::mister::transport::PALETTE_BYTES;
using diablo::mister::transport::PCM_REGION_OFFSET;
using diablo::mister::transport::SHARED_BYTES;

constexpr off_t kPhysicalBase = 0x3FE00000;
constexpr uint32_t kEpoch = 0xD1A61001;

enum class ExpectedResult { Ready, Fault };

int fail(const char *message)
{
    std::fprintf(stderr, "transport-header-probe: %s: %s\n", message, std::strerror(errno));
    return 1;
}

int selfTest()
{
    std::vector<std::byte> storage(SHARED_BYTES + alignof(Header));
    const auto start = reinterpret_cast<uintptr_t>(storage.data());
    const auto aligned = (start + alignof(Header) - 1) & ~(static_cast<uintptr_t>(alignof(Header)) - 1);
    auto attachment = AbiView::Attach({ reinterpret_cast<std::byte *>(aligned), SHARED_BYTES });
    if (!attachment.has_value() || !attachment->InitializeArm(kEpoch)
        || !attachment->Validate(kEpoch).has_value()) {
        std::fputs("transport-header-probe self-test: ABI initialization failed\n", stderr);
        return 1;
    }
    Header &header = attachment->header();
    if (header.arm_state != static_cast<uint32_t>(ComponentState::Ready)
        || header.fpga_state != static_cast<uint32_t>(ComponentState::Offline)) {
        std::fputs("transport-header-probe self-test: unexpected initial component state\n", stderr);
        return 1;
    }
    auto frame = attachment->ArmBeginFrame(0, kEpoch);
    if (!frame.has_value() || !attachment->ArmPublishFrame(0, kEpoch, 1, 1, 1, 0, FRAME_CHECKSUM_ABSENT)
        || header.frames[0].state != static_cast<uint32_t>(FrameState::Ready)) {
        std::fputs("transport-header-probe self-test: frame publication failed\n", stderr);
        return 1;
    }
    const std::array<std::array<std::int16_t, 2>, 2> pcm = {{{0x1000, 0x2000}, {-0x1000, -0x2000}}};
    if (!attachment->ArmPublishPcm(pcm, kEpoch)
        || header.pcm.producer_sequence != 2
        || storage[aligned - start + PCM_REGION_OFFSET] != std::byte {0x00}) {
        std::fputs("transport-header-probe self-test: PCM publication failed\n", stderr);
        return 1;
    }
    std::puts("transport-header-probe self-test: passed");
    return 0;
}

int flushDeviceMapping(void *mapping)
{
    errno = 0;
    if (msync(mapping, 4096, MS_SYNC) == 0) return 0;
    if (errno == EINVAL) {
        // MiSTer's O_SYNC /dev/mem mappings have no page-cache backing. The
        // release fence plus this ARM barrier order the stores for FPGA reads.
        __sync_synchronize();
        std::fputs("transport-header-probe: O_SYNC device mapping uses ARM barrier\n", stderr);
        return 0;
    }
    return fail("flush control page");
}

int awaitResult(const AbiView &view, ExpectedResult expected)
{
    Header &header = view.header();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (std::chrono::steady_clock::now() < deadline) {
        const uint32_t fpgaState = std::atomic_ref<uint32_t>(header.fpga_state).load(std::memory_order_acquire);
        if (expected == ExpectedResult::Ready && fpgaState == static_cast<uint32_t>(ComponentState::Ready)) {
            std::printf("transport-header-probe: passed epoch=0x%08" PRIx32 " fpga_state=ready\n", header.session_epoch);
            return 0;
        }
        if (expected == ExpectedResult::Fault && fpgaState == static_cast<uint32_t>(ComponentState::Fault)) {
            std::printf("transport-header-probe: expected fault code=%" PRIu32 " detail=0x%08" PRIx32 "\n",
                        header.fault_code, header.fault_detail);
            return 0;
        }
        __sync_synchronize();
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::fprintf(stderr, "transport-header-probe: timed out fpga_state=%" PRIu32
                         " fault_code=%" PRIu32 " fault_detail=0x%08" PRIx32 "\n",
                 header.fpga_state, header.fault_code, header.fault_detail);
    return 1;
}

int publishTestFrame(const AbiView &view, void *mapping, uint32_t slot, uint64_t frameId,
                     uint8_t patternPhase)
{
    auto frame = view.ArmBeginFrame(slot, kEpoch);
    if (!frame.has_value()) {
        std::fputs("transport-header-probe: cannot acquire test frame slot\n", stderr);
        return 1;
    }

    auto memory = view.memory();
    auto pixels = memory.subspan(FrameOffset(slot), FRAME_PIXEL_BYTES);
    auto palette = memory.subspan(PaletteOffset(slot), PALETTE_BYTES);
    for (uint32_t y = 0; y < FRAME_HEIGHT; ++y) {
        for (uint32_t x = 0; x < FRAME_WIDTH; ++x) {
            const uint8_t index = static_cast<uint8_t>(((x >> 5) + (y >> 5) * 20 + patternPhase) & 0xff);
            pixels[y * FRAME_WIDTH + x] = static_cast<std::byte>(index);
        }
    }
    for (uint32_t index = 0; index < 256; ++index) {
        palette[index * 3 + 0] = static_cast<std::byte>((index + patternPhase) & 0xff);
        palette[index * 3 + 1] = static_cast<std::byte>((255 - index + patternPhase) & 0xff);
        palette[index * 3 + 2] = static_cast<std::byte>((index * 37 + patternPhase) & 0xff);
    }
    std::atomic_thread_fence(std::memory_order_release);
    if (flushDeviceMapping(mapping) != 0
        || !view.ArmPublishFrame(slot, kEpoch, frameId, 1, 1, 0, FRAME_CHECKSUM_ABSENT)
        || flushDeviceMapping(mapping) != 0) {
        std::fputs("transport-header-probe: test frame publication failed\n", stderr);
        return 1;
    }

    Header &header = view.header();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (std::chrono::steady_clock::now() < deadline) {
        const uint32_t state = std::atomic_ref<uint32_t>(header.frames[slot].state).load(std::memory_order_acquire);
        if (state == static_cast<uint32_t>(FrameState::FpgaDisplaying)) {
            std::printf("transport-header-probe: test frame %" PRIu64 " published and claimed by FPGA\n", frameId);
            return 0;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::fprintf(stderr, "transport-header-probe: test frame was not claimed (state=%" PRIu32 ")\n",
                 header.frames[slot].state);
    return 1;
}

int publishTwoTestFrames(const AbiView &view, void *mapping)
{
    if (publishTestFrame(view, mapping, 0, 1, 0) != 0) return 1;
    if (publishTestFrame(view, mapping, 1, 2, 73) != 0) return 1;

    Header &header = view.header();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(3);
    while (std::chrono::steady_clock::now() < deadline) {
        const uint32_t retiredState = std::atomic_ref<uint32_t>(header.frames[0].state).load(std::memory_order_acquire);
        if (retiredState == static_cast<uint32_t>(FrameState::Free)) {
            std::puts("transport-header-probe: retired frame slot reclaimed by FPGA");
            return 0;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::fprintf(stderr, "transport-header-probe: retired frame was not reclaimed (state=%" PRIu32 ")\n",
                 header.frames[0].state);
    return 1;
}

int publishPcmTest(const AbiView &view, void *mapping)
{
    std::array<std::array<std::int16_t, 2>, 480> samples {};
    for (uint32_t index = 0; index < samples.size(); ++index) {
        samples[index][0] = static_cast<std::int16_t>((index * 97) - 23000);
        samples[index][1] = static_cast<std::int16_t>(23000 - (index * 61));
    }
    if (!view.ArmPublishPcm(samples, kEpoch) || flushDeviceMapping(mapping) != 0) {
        std::fputs("transport-header-probe: PCM test publication failed\n", stderr);
        return 1;
    }

    Header &header = view.header();
    const uint32_t expected = header.pcm.producer_sequence;
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (std::chrono::steady_clock::now() < deadline) {
        const uint32_t consumed = std::atomic_ref<uint32_t>(header.pcm.consumer_sequence)
                                      .load(std::memory_order_acquire);
        if (consumed == expected) {
            std::puts("transport-header-probe: PCM queue primed and consumed by FPGA");
            return 0;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::fprintf(stderr, "transport-header-probe: PCM queue was not consumed (producer=%" PRIu32
                         " consumer=%" PRIu32 ")\n",
                 header.pcm.producer_sequence, header.pcm.consumer_sequence);
    return 1;
}

int inputIdleTest(const AbiView &view)
{
    Header &header = view.header();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (std::chrono::steady_clock::now() < deadline) {
        const uint32_t producer = std::atomic_ref<uint32_t>(header.input.producer_sequence)
                                      .load(std::memory_order_acquire);
        const uint32_t consumer = std::atomic_ref<uint32_t>(header.input.consumer_sequence)
                                      .load(std::memory_order_acquire);
        if (producer != 0 || consumer != 0) {
            std::fprintf(stderr, "transport-header-probe: unexpected idle input cursor producer=%" PRIu32
                                 " consumer=%" PRIu32 "\n", producer, consumer);
            return 1;
        }
        if (header.input.capacity != INPUT_CAPACITY
            || header.input.record_bytes != INPUT_RECORD_BYTES
            || header.input.epoch != kEpoch) {
            std::fputs("transport-header-probe: input ring ABI changed while idle\n", stderr);
            return 1;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    std::puts("transport-header-probe: input ring attached and idle");
    return 0;
}
} // namespace

int main(int argc, char **argv)
{
    if (argc == 2 && std::strcmp(argv[1], "--self-test") == 0) return selfTest();

    ExpectedResult expected = ExpectedResult::Ready;
    bool malformedMagic = false;
    bool staleSlot = false;
    bool prepareOnly = false;
    bool observeOnly = false;
    bool publishTestFrameRequested = false;
    bool publishTwoTestFramesRequested = false;
    bool publishPcmTestRequested = false;
    bool inputIdleTestRequested = false;
    if (argc == 2 && std::strcmp(argv[1], "--malformed-magic") == 0) {
        expected = ExpectedResult::Fault;
        malformedMagic = true;
    } else if (argc == 2 && std::strcmp(argv[1], "--stale-slot") == 0) {
        expected = ExpectedResult::Fault;
        staleSlot = true;
    } else if (argc == 2 && std::strcmp(argv[1], "--prepare-malformed-magic") == 0) {
        malformedMagic = true;
        prepareOnly = true;
    } else if (argc == 2 && std::strcmp(argv[1], "--prepare-stale-slot") == 0) {
        staleSlot = true;
        prepareOnly = true;
    } else if (argc == 2 && std::strcmp(argv[1], "--await-fault") == 0) {
        expected = ExpectedResult::Fault;
        observeOnly = true;
    } else if (argc == 2 && std::strcmp(argv[1], "--publish-test-frame") == 0) {
        publishTestFrameRequested = true;
    } else if (argc == 2 && std::strcmp(argv[1], "--publish-two-test-frames") == 0) {
        publishTwoTestFramesRequested = true;
    } else if (argc == 2 && std::strcmp(argv[1], "--publish-pcm-test") == 0) {
        publishPcmTestRequested = true;
    } else if (argc == 2 && std::strcmp(argv[1], "--input-idle-test") == 0) {
        inputIdleTestRequested = true;
    } else if (argc != 1) {
        std::fprintf(stderr, "usage: %s [--self-test|--malformed-magic|--stale-slot|--prepare-malformed-magic|--prepare-stale-slot|--await-fault|--publish-test-frame|--publish-two-test-frames|--publish-pcm-test|--input-idle-test]\n", argv[0]);
        return 2;
    }

    const int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) return fail("open /dev/mem");
    void *mapping = mmap(nullptr, SHARED_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, fd, kPhysicalBase);
    if (mapping == MAP_FAILED) {
        const int result = fail("map shared-DDR reservation");
        close(fd);
        return result;
    }

    int result = 1;
    auto attachment = AbiView::Attach({ static_cast<std::byte *>(mapping), SHARED_BYTES });
    if (!attachment.has_value()) {
        std::fprintf(stderr, "transport-header-probe: ABI attachment failed (%u)\n",
                     static_cast<unsigned>(attachment.error()));
    } else if (observeOnly) {
        result = awaitResult(*attachment, expected);
    } else if (!attachment->InitializeArm(kEpoch)) {
        std::fputs("transport-header-probe: ABI initialization rejected epoch\n", stderr);
    } else {
        Header &header = attachment->header();
        if (malformedMagic) header.magic[0] = 'X';
        if (staleSlot) header.frames[0].generation = kEpoch + 1;
        __sync_synchronize();
        if (flushDeviceMapping(mapping) == 0) {
            if (prepareOnly) {
                std::printf("transport-header-probe: prepared %s header\n",
                            malformedMagic ? "malformed-magic" : "stale-slot");
                result = 0;
            } else if (publishTestFrameRequested) {
                result = awaitResult(*attachment, ExpectedResult::Ready);
                if (result == 0) result = publishTestFrame(*attachment, mapping, 0, 1, 0);
            } else if (publishTwoTestFramesRequested) {
                result = awaitResult(*attachment, ExpectedResult::Ready);
                if (result == 0) result = publishTwoTestFrames(*attachment, mapping);
            } else if (publishPcmTestRequested) {
                result = awaitResult(*attachment, ExpectedResult::Ready);
                if (result == 0) result = publishPcmTest(*attachment, mapping);
            } else if (inputIdleTestRequested) {
                result = awaitResult(*attachment, ExpectedResult::Ready);
                if (result == 0) result = inputIdleTest(*attachment);
            } else {
                result = awaitResult(*attachment, expected);
            }
        }
    }

    munmap(mapping, SHARED_BYTES);
    close(fd);
    return result;
}
