#include "mister_transport_admission.hpp"

#include <cassert>
#include <cstdint>
#include <limits>
#include <string>

using namespace diablo::mister::transport;

int main()
{
	auto aperture = ParsePhysicalAperture("0x3FE00000", 2U * 1024U * 1024U, 4096,
	                                     std::numeric_limits<std::uint64_t>::max());
	assert(aperture.has_value());
	assert(aperture->requested_base == 0x3FE00000ULL);
	assert(aperture->page_base == 0x3FE00000ULL);
	assert(aperture->page_offset == 0U);
	assert(aperture->mapped_bytes == 2U * 1024U * 1024U);

	for (const char *bad : { "", "-1", "+1", " 1", "1 ", "0x", "0x100q", "1junk" }) {
		assert(!ParsePhysicalAperture(bad, 4096, 4096,
		                              std::numeric_limits<std::uint64_t>::max()).has_value());
	}
	assert(!ParsePhysicalAperture("0x1000", 4096, 3000,
	                              std::numeric_limits<std::uint64_t>::max()).has_value());
	assert(!ParsePhysicalAperture("0xffffffffffffffff", 2, 4096,
	                              std::numeric_limits<std::uint64_t>::max()).has_value());
	assert(!ParsePhysicalAperture("0x80000000", 4096, 4096, 0x7fffffffULL).has_value());

	const std::string candidate(64, 'a');
	const std::string record = "schema=diablo-reserved-ddr-admission-v1\n"
	                           "boot_id=01234567-89ab-cdef-0123-456789abcdef\n"
	                           "physical_base=0x3FE00000\n"
	                           "bytes=2097152\n"
	                           "candidate_id=" + candidate + "\n";
	auto admission = ParseBootAdmission(record);
	assert(admission.has_value());
	assert(admission->physical_base == 0x3FE00000ULL);
	assert(admission->bytes == 2097152ULL);
	assert(admission->candidate_id == candidate);
	assert(!ParseBootAdmission(record + "bytes=1\n").has_value());
	assert(!ParseBootAdmission("schema=diablo-reserved-ddr-admission-v1\n").has_value());
	return 0;
}
