#pragma once

#include <charconv>
#include <cstddef>
#include <cstdint>
#include <expected>
#include <limits>
#include <string>
#include <string_view>

namespace diablo::mister::transport {

enum class AdmissionError : std::uint32_t {
	InvalidInteger,
	InvalidAperture,
	MalformedRecord,
};

struct PhysicalAperture {
	std::uint64_t requested_base = 0;
	std::uint64_t page_base = 0;
	std::size_t page_offset = 0;
	std::size_t mapped_bytes = 0;
};

struct BootAdmission {
	std::string boot_id;
	std::uint64_t physical_base = 0;
	std::uint64_t bytes = 0;
	std::string candidate_id;
};

[[nodiscard]] inline std::expected<std::uint64_t, AdmissionError> ParseUnsigned(
	std::string_view text)
{
	if (text.empty() || text.front() == '+' || text.front() == '-') {
		return std::unexpected(AdmissionError::InvalidInteger);
	}
	unsigned base = 10;
	if (text.size() >= 2 && text[0] == '0' && (text[1] == 'x' || text[1] == 'X')) {
		base = 16;
		text.remove_prefix(2);
		if (text.empty()) return std::unexpected(AdmissionError::InvalidInteger);
	}
	std::uint64_t value = 0;
	auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value, base);
	if (error != std::errc() || end != text.data() + text.size()) {
		return std::unexpected(AdmissionError::InvalidInteger);
	}
	return value;
}

[[nodiscard]] inline std::expected<PhysicalAperture, AdmissionError> ParsePhysicalAperture(
	std::string_view text, std::size_t shared_bytes, std::uint64_t page_size,
	std::uint64_t maximum_offset)
{
	auto requested = ParseUnsigned(text);
	if (!requested.has_value() || shared_bytes == 0 || page_size == 0
		|| (page_size & (page_size - 1U)) != 0) {
		return std::unexpected(AdmissionError::InvalidAperture);
	}
	const std::uint64_t page_mask = page_size - 1U;
	const std::uint64_t page_base = *requested & ~page_mask;
	const std::uint64_t page_offset = *requested - page_base;
	if (page_offset > std::numeric_limits<std::size_t>::max()
		|| shared_bytes > std::numeric_limits<std::size_t>::max() - page_offset) {
		return std::unexpected(AdmissionError::InvalidAperture);
	}
	// mmap's offset and every byte consumed by the aperture must be representable
	// by off_t. This rules out a successful uint64 parse followed by a truncating
	// cast to the platform mapping offset.
	if (*requested > maximum_offset
		|| static_cast<std::uint64_t>(shared_bytes - 1U) > maximum_offset - *requested) {
		return std::unexpected(AdmissionError::InvalidAperture);
	}
	return PhysicalAperture {
		.requested_base = *requested,
		.page_base = page_base,
		.page_offset = static_cast<std::size_t>(page_offset),
		.mapped_bytes = static_cast<std::size_t>(page_offset) + shared_bytes,
	};
}

[[nodiscard]] inline bool IsCandidateId(std::string_view value)
{
	if (value.size() != 64) return false;
	for (const char character : value) {
		if (!((character >= '0' && character <= '9') || (character >= 'a' && character <= 'f'))) {
			return false;
		}
	}
	return true;
}

[[nodiscard]] inline std::expected<BootAdmission, AdmissionError> ParseBootAdmission(
	std::string_view record)
{
	BootAdmission result;
	bool schema = false;
	bool boot_id = false;
	bool physical_base = false;
	bool bytes = false;
	bool candidate_id = false;
	while (!record.empty()) {
		const std::size_t newline = record.find('\n');
		std::string_view line = record.substr(0, newline);
		record.remove_prefix(newline == std::string_view::npos ? record.size() : newline + 1U);
		if (!line.empty() && line.back() == '\r') line.remove_suffix(1);
		if (line.empty()) continue;
		const std::size_t equals = line.find('=');
		if (equals == std::string_view::npos) return std::unexpected(AdmissionError::MalformedRecord);
		const std::string_view key = line.substr(0, equals);
		const std::string_view value = line.substr(equals + 1U);
		if (key == "schema" && !schema && value == "diablo-reserved-ddr-admission-v1") {
			schema = true;
		} else if (key == "boot_id" && !boot_id && !value.empty()) {
			result.boot_id = value;
			boot_id = true;
		} else if (key == "physical_base" && !physical_base) {
			auto parsed = ParseUnsigned(value);
			if (!parsed.has_value()) return std::unexpected(AdmissionError::MalformedRecord);
			result.physical_base = *parsed;
			physical_base = true;
		} else if (key == "bytes" && !bytes) {
			auto parsed = ParseUnsigned(value);
			if (!parsed.has_value()) return std::unexpected(AdmissionError::MalformedRecord);
			result.bytes = *parsed;
			bytes = true;
		} else if (key == "candidate_id" && !candidate_id && IsCandidateId(value)) {
			result.candidate_id = value;
			candidate_id = true;
		} else {
			return std::unexpected(AdmissionError::MalformedRecord);
		}
	}
	if (!schema || !boot_id || !physical_base || !bytes || !candidate_id) {
		return std::unexpected(AdmissionError::MalformedRecord);
	}
	return result;
}

} // namespace diablo::mister::transport
