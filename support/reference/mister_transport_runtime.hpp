#pragma once

#include "mister_transport.hpp"
#include "mister_transport_admission.hpp"

#include <atomic>
#include <charconv>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <expected>
#include <fcntl.h>
#include <limits>
#include <string>
#include <sys/file.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

namespace diablo::mister::transport {

enum class RuntimeError : std::uint32_t {
	MissingSource,
	InvalidSource,
	OpenFailed,
	MapFailed,
	BadAttachment,
	BadEpoch,
	AdmissionFailed,
	OwnershipFailed,
};

// A flock is released by the kernel when its owning process dies. That gives
// launch, runtime and diagnostics one liveness-based ownership primitive and
// avoids treating an old pathname as evidence that a writer still owns DDR.
class TransportLease {
public:
	TransportLease() = default;
	TransportLease(const TransportLease &) = delete;
	TransportLease &operator=(const TransportLease &) = delete;
	TransportLease(TransportLease &&other) noexcept : fd_(other.fd_) { other.fd_ = -1; }
	TransportLease &operator=(TransportLease &&other) noexcept
	{
		if (this != &other) {
			Release();
			fd_ = other.fd_;
			other.fd_ = -1;
		}
		return *this;
	}
	~TransportLease() { Release(); }

	[[nodiscard]] static std::expected<TransportLease, RuntimeError> Acquire()
	{
		const char *path = std::getenv("DIABLO_MISTER_TRANSPORT_LOCK");
		if (path == nullptr || *path == '\0') return std::unexpected(RuntimeError::OwnershipFailed);
		const char *inherited_text = std::getenv("DIABLO_MISTER_TRANSPORT_LOCK_FD");
		if (inherited_text != nullptr && *inherited_text != '\0') {
		#ifndef _WIN32
			// The project launcher owns the lock while it supervises the child.
			// Adopt a duplicate of that already-locked descriptor instead of
			// opening the pathname a second time (which would race/fail while the
			// parent still holds the flock).  An injected descriptor is accepted
			// only when it names the exact no-symlink lock path from the env.
			auto parsed = ParseUnsigned(inherited_text);
			if (!parsed.has_value() || *parsed > static_cast<std::uint64_t>(std::numeric_limits<int>::max()))
				return std::unexpected(RuntimeError::OwnershipFailed);
			const int inherited = static_cast<int>(*parsed);
			struct stat inherited_status {};
			if (::fstat(inherited, &inherited_status) != 0 || !S_ISREG(inherited_status.st_mode))
				return std::unexpected(RuntimeError::OwnershipFailed);
			const int expected = ::open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
			if (expected < 0) return std::unexpected(RuntimeError::OwnershipFailed);
			struct stat expected_status {};
			const bool same_file = ::fstat(expected, &expected_status) == 0
				&& inherited_status.st_dev == expected_status.st_dev
				&& inherited_status.st_ino == expected_status.st_ino;
			::close(expected);
			if (!same_file) return std::unexpected(RuntimeError::OwnershipFailed);
			// Reassert exclusive ownership only after identity validation. A
			// launcher child normally shares the parent's flock; an injected but
			// unlocked descriptor must not be mistaken for a valid lease or leave
			// an unrelated file locked on a failed admission.
			if (::flock(inherited, LOCK_EX | LOCK_NB) != 0)
				return std::unexpected(RuntimeError::OwnershipFailed);
			const int duplicate = ::fcntl(inherited, F_DUPFD_CLOEXEC, 3);
			if (duplicate < 0) return std::unexpected(RuntimeError::OwnershipFailed);
			return TransportLease(duplicate);
		#else
			// The production target is Linux, where the POSIX descriptor hand-off
			// above is available.  The Windows host build has no equivalent
			// TransportRuntime implementation; reject an unadoptable descriptor
			// instead of silently reopening a lock held by the launcher.
			return std::unexpected(RuntimeError::OwnershipFailed);
		#endif
		}
		const int fd = ::open(path, O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW, 0600);
		if (fd < 0) return std::unexpected(RuntimeError::OwnershipFailed);
		if (::flock(fd, LOCK_EX | LOCK_NB) != 0) {
			::close(fd);
			return std::unexpected(RuntimeError::OwnershipFailed);
		}
		return TransportLease(fd);
	}

private:
	explicit TransportLease(int fd) : fd_(fd) {}
	void Release()
	{
		if (fd_ >= 0) {
			(void)::flock(fd_, LOCK_UN);
			(void)::close(fd_);
			fd_ = -1;
		}
	}
	int fd_ = -1;
};

// Maps the already-admitted 2 MiB reservation without baking a physical DDR
// address into the ABI. Production launches must provide
// DIABLO_MISTER_SHARED_PHYS explicitly; file-backed mappings are for QEMU and
// deterministic integration tests only.
class TransportRuntime {
public:
	// Diagnostics that map the aperture directly must use this same admission
	// check before their first write. It binds the current boot, exact aperture
	// and requested candidate ID to the launcher-produced admission record.
	[[nodiscard]] static bool HasCurrentBootAdmission(const PhysicalAperture &aperture)
	{
		return ValidateCurrentBootAdmission(aperture);
	}

	static std::expected<TransportRuntime, RuntimeError> Open()
	{
		const char *path = std::getenv("DIABLO_MISTER_SHARED_PATH");
		const char *physical = std::getenv("DIABLO_MISTER_SHARED_PHYS");
		if ((path == nullptr || *path == '\0')
		    && (physical == nullptr || *physical == '\0'))
			return std::unexpected(RuntimeError::MissingSource);
		if (path != nullptr && *path != '\0' && physical != nullptr && *physical != '\0')
			return std::unexpected(RuntimeError::InvalidSource);

		int fd = -1;
		void *mapping = MAP_FAILED;
		std::size_t mapped_bytes = SHARED_BYTES;
		std::size_t offset = 0;
		bool device_mapping = false;
		PhysicalAperture aperture {};
		if (path == nullptr || *path == '\0') {
			device_mapping = true;
			const long page_size = ::sysconf(_SC_PAGESIZE);
			if (page_size <= 0) return std::unexpected(RuntimeError::InvalidSource);
			auto parsed_aperture = ParsePhysicalAperture(
				physical, SHARED_BYTES, static_cast<std::uint64_t>(page_size),
				static_cast<std::uint64_t>(std::numeric_limits<off_t>::max()));
			if (!parsed_aperture.has_value())
				return std::unexpected(RuntimeError::InvalidSource);
			aperture = *parsed_aperture;
			if (!ValidateCurrentBootAdmission(aperture))
				return std::unexpected(RuntimeError::AdmissionFailed);
			offset = aperture.page_offset;
			mapped_bytes = aperture.mapped_bytes;
		}
		// File-backed/QEMU mappings are also shared transport state. Require the
		// same liveness-based lease as /dev/mem so a direct probe cannot race a
		// launched game. The launcher-provided descriptor is adopted when present.
		TransportLease lease;
		auto acquired = TransportLease::Acquire();
		if (!acquired.has_value()) return std::unexpected(acquired.error());
		lease = std::move(*acquired);
		if (path != nullptr && *path != '\0') {
			fd = ::open(path, O_RDWR | O_CLOEXEC | O_NOFOLLOW);
			if (fd < 0) return std::unexpected(RuntimeError::OpenFailed);
			const off_t length = ::lseek(fd, 0, SEEK_END);
			if (length < static_cast<off_t>(SHARED_BYTES) || ::lseek(fd, 0, SEEK_SET) < 0) {
				::close(fd);
				return std::unexpected(RuntimeError::InvalidSource);
			}
			mapping = ::mmap(nullptr, SHARED_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
		} else {
			fd = ::open("/dev/mem", O_RDWR | O_SYNC | O_CLOEXEC);
			if (fd < 0) return std::unexpected(RuntimeError::OpenFailed);
			mapping = ::mmap(nullptr, mapped_bytes, PROT_READ | PROT_WRITE,
			                 MAP_SHARED, fd, static_cast<off_t>(aperture.page_base));
		}
		if (mapping == MAP_FAILED) {
			if (fd >= 0) ::close(fd);
			return std::unexpected(RuntimeError::MapFailed);
		}

		auto attached = AbiView::Attach({
		    static_cast<std::byte *>(mapping) + offset, SHARED_BYTES});
		if (!attached.has_value()) {
			::munmap(mapping, mapped_bytes);
			::close(fd);
			return std::unexpected(RuntimeError::BadAttachment);
		}
		const std::uint32_t epoch = ReadEpoch();
		if (epoch == 0 || !attached->InitializeArm(epoch)) {
			::munmap(mapping, mapped_bytes);
			::close(fd);
			return std::unexpected(RuntimeError::BadEpoch);
		}
		TransportRuntime runtime(fd, mapping, mapped_bytes,
		                         TransportSession(*attached, epoch), offset,
		                         device_mapping, std::move(lease));
		// Publish the freshly initialized control page before the engine can
		// submit its first frame. Device mappings commonly reject msync with
		// EINVAL; Flush() handles that case with the ARM synchronization barrier.
		if (!runtime.Flush())
			return std::unexpected(RuntimeError::MapFailed);
		return runtime;
	}

	TransportRuntime(const TransportRuntime &) = delete;
	TransportRuntime &operator=(const TransportRuntime &) = delete;
	TransportRuntime(TransportRuntime &&other) noexcept
		: fd_(other.fd_)
		, mapping_(other.mapping_)
		, mapped_bytes_(other.mapped_bytes_)
		, offset_(other.offset_)
		, device_mapping_(other.device_mapping_)
		, session_(other.session_)
		, lease_(std::move(other.lease_))
	{
		other.fd_ = -1;
		other.mapping_ = MAP_FAILED;
		other.mapped_bytes_ = 0;
		other.device_mapping_ = false;
	}
	TransportRuntime &operator=(TransportRuntime &&) = delete;

	~TransportRuntime()
	{
		(void)Flush();
		if (mapping_ != MAP_FAILED) ::munmap(mapping_, mapped_bytes_);
		if (fd_ >= 0) ::close(fd_);
	}

	[[nodiscard]] TransportSession &session() { return session_; }
	[[nodiscard]] const TransportSession &session() const { return session_; }

	// Recover an ARM process that stayed alive across a MiSTer core reload. The
	// control reader deliberately faults on stale in-flight slots; once that
	// fault is visible, clear the control page and publish a fresh epoch so the
	// reader can attach again without reopening the device mapping.
	[[nodiscard]] bool RecoverAfterFpgaFault()
	{
		if (mapping_ == MAP_FAILED) return false;
		auto &header = session_.view().header();
		if (std::atomic_ref<std::uint32_t>(header.fpga_state).load(std::memory_order_acquire)
		    != static_cast<std::uint32_t>(ComponentState::Fault))
			return false;
		std::uint32_t fresh_epoch = GenerateEpoch();
		if (fresh_epoch == session_.epoch()) ++fresh_epoch;
		if (fresh_epoch == 0 || !session_.view().InitializeArm(fresh_epoch)) return false;
		session_.RebindEpoch(fresh_epoch);
		return Flush();
	}

	// The FPGA control reader may need a few milliseconds after the ARM
	// publication marker becomes visible. Wait once before the first frame so
	// startup does not turn attachment latency into repeated frame backpressure.
	[[nodiscard]] bool WaitForFpgaReady(unsigned timeout_ms) const
	{
		if (mapping_ == MAP_FAILED) return false;
		auto &header = session_.view().header();
		std::atomic_ref<std::uint32_t> state(header.fpga_state);
		const timespec delay { 0, 1'000'000 };
		for (unsigned elapsed = 0; elapsed < timeout_ms; ++elapsed) {
			const auto value = state.load(std::memory_order_acquire);
			if (value == static_cast<std::uint32_t>(ComponentState::Ready)) return true;
			// A live RBF reload can expose Fault for one bounded reader retry
			// before the same ARM page is accepted again. Keep waiting within the
			// caller's deadline instead of converting that transient into a startup
			// failure and an unnecessary frame fallback.
			(void)::nanosleep(&delay, nullptr);
		}
		return false;
	}

	// msync is useful for file-backed QEMU fixtures. Device mappings can reject
	// it with EINVAL; the ARM barrier still orders the stores for the FPGA port.
	[[nodiscard]] bool Flush() const
	{
		if (mapping_ == MAP_FAILED) return false;
		if (device_mapping_) {
			// O_SYNC /dev/mem mappings do not need a syscall per frame. The
			// compiler/CPU barrier orders descriptor and pixel stores before
			// the FPGA observes the published state.
			__sync_synchronize();
			return true;
		}
		if (::msync(mapping_, mapped_bytes_, MS_SYNC) == 0) return true;
		if (errno == EINVAL) {
			__sync_synchronize();
			return true;
		}
		return false;
	}

private:
	TransportRuntime(int fd, void *mapping, std::size_t mapped_bytes,
	                TransportSession session, std::size_t offset,
	                bool device_mapping, TransportLease lease)
		: fd_(fd)
		, mapping_(mapping)
		, mapped_bytes_(mapped_bytes)
		, offset_(offset)
		, device_mapping_(device_mapping)
		, session_(session)
		, lease_(std::move(lease))
	{
	}

	static std::uint32_t GenerateEpoch()
	{
		struct timespec now {};
		if (::clock_gettime(CLOCK_MONOTONIC, &now) != 0) return 0;
		const auto ticks = static_cast<std::uint64_t>(now.tv_sec) * 1000000000ULL
		                 + static_cast<std::uint64_t>(now.tv_nsec);
		const auto generated = static_cast<std::uint32_t>(ticks ^ (ticks >> 32U)
		                                                    ^ static_cast<std::uint64_t>(::getpid()));
		return generated == 0 ? 1U : generated;
	}

	static std::uint32_t ReadEpoch()
	{
		const char *value = std::getenv("DIABLO_MISTER_SESSION_EPOCH");
		if (value != nullptr && *value != '\0') {
			auto parsed = ParseUnsigned(value);
			if (parsed.has_value() && *parsed != 0
				&& *parsed <= std::numeric_limits<std::uint32_t>::max())
				return static_cast<std::uint32_t>(*parsed);
			return 0;
		}
		return GenerateEpoch();
	}

	[[nodiscard]] static std::expected<std::string, RuntimeError> ReadSmallTextFile(
	    const char *path, bool require_regular = true)
	{
		if (path == nullptr || *path == '\0') return std::unexpected(RuntimeError::AdmissionFailed);
		const int fd = ::open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
		if (fd < 0) return std::unexpected(RuntimeError::AdmissionFailed);
		struct stat status {};
		if (::fstat(fd, &status) != 0 || (require_regular && !S_ISREG(status.st_mode))) {
			::close(fd);
			return std::unexpected(RuntimeError::AdmissionFailed);
		}
		std::string result;
		char buffer[256] {};
		for (;;) {
			const ssize_t read_now = ::read(fd, buffer, sizeof(buffer));
			if (read_now < 0 || result.size() + static_cast<std::size_t>(read_now) > 4096) {
				::close(fd);
				return std::unexpected(RuntimeError::AdmissionFailed);
			}
			if (read_now == 0) break;
			result.append(buffer, static_cast<std::size_t>(read_now));
		}
		::close(fd);
		if (result.empty()) return std::unexpected(RuntimeError::AdmissionFailed);
		return result;
	}

	[[nodiscard]] static bool ValidateCurrentBootAdmission(const PhysicalAperture &aperture)
	{
		const char *candidate = std::getenv("DIABLO_MISTER_CANDIDATE_ID");
		if (candidate == nullptr || !IsCandidateId(candidate)) return false;
		auto record_text = ReadSmallTextFile(std::getenv("DIABLO_MISTER_ADMISSION_FILE"));
		auto boot_id = ReadSmallTextFile("/proc/sys/kernel/random/boot_id", false);
		if (!record_text.has_value() || !boot_id.has_value()) return false;
		while (!boot_id->empty() && (boot_id->back() == '\n' || boot_id->back() == '\r')) {
			boot_id->pop_back();
		}
		auto record = ParseBootAdmission(*record_text);
		return record.has_value() && record->boot_id == *boot_id
		    && record->physical_base == aperture.requested_base
		    && record->bytes == SHARED_BYTES && record->candidate_id == candidate;
	}

	int fd_;
	void *mapping_;
	std::size_t mapped_bytes_;
	std::size_t offset_;
	bool device_mapping_;
	TransportSession session_;
	TransportLease lease_;
};

} // namespace diablo::mister::transport
