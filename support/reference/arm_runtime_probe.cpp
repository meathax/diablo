// Standalone target ABI probe. Run on the MiSTer before admitting a toolchain.
// This is a correctness/runtime check, not a performance benchmark.
#include <arm_neon.h>
#include <array>
#include <atomic>
#include <bit>
#include <cstdio>
#include <expected>
#include <format>
#include <thread>
#include <sys/utsname.h>
#include <unistd.h>

static_assert(sizeof(void *) == 4);
static_assert(std::endian::native == std::endian::little);
static_assert(std::atomic<unsigned>::is_always_lock_free);

int main(int argc, char **)
{
    // Runtime-dependent inputs keep this an actual NEON operation.
    const unsigned n = static_cast<unsigned>(argc);
    const std::array<unsigned, 4> input {n, n + 1, n + 2, n + 3};
    std::array<unsigned, 4> output {};
    vst1q_u32(output.data(), vaddq_u32(vld1q_u32(input.data()), vdupq_n_u32(7)));
    for (unsigned i = 0; i < output.size(); ++i)
        if (output[i] != input[i] + 7) return 2;

    std::atomic<unsigned> published {0};
    std::thread worker([&] { published.store(output[3], std::memory_order_release); });
    worker.join();
    const std::expected<unsigned, const char *> result = published.load(std::memory_order_acquire);
    if (!result || *result != n + 10) return 3;
    utsname system {};
    if (uname(&system) != 0) return 4;
    const auto report = std::format(
        "ARM runtime probe PASS: machine={}, kernel={}, pointer_bits={}, online_cpus={}, page_bytes={}, neon_result={}\n",
        system.machine, system.release, sizeof(void *) * 8,
        sysconf(_SC_NPROCESSORS_ONLN), sysconf(_SC_PAGESIZE), *result);
    std::fputs(report.c_str(), stdout);
}
