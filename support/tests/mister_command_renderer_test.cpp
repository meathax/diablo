#include "mister_command_renderer.hpp"
#include "mister_command_scene.hpp"

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstdint>
#include <iostream>
#include <limits>
#include <vector>

using diablo::mister::command::Buffer;
using diablo::mister::command::Record;
using diablo::mister::command::SoftwareRenderer;
using diablo::mister::command::BuildChangedRuns;

namespace {

void Require(bool condition, const char *message)
{
	if (!condition) {
		std::cerr << message << '\n';
		std::exit(1);
	}
}

void ReferenceCopy(std::vector<std::uint8_t> &pixels, std::size_t pitch,
                   std::int32_t width, std::int32_t height, Record record)
{
	const auto source_x = static_cast<std::int16_t>(record.payload_offset & 0xffffU);
	const auto source_y = static_cast<std::int16_t>(record.payload_offset >> 16U);
	const std::int32_t left = std::max({ 0, -record.x, -source_x });
	const std::int32_t top = std::max({ 0, -record.y, -source_y });
	const std::int32_t right = std::min({ record.width, width - record.x,
	                                      width - source_x });
	const std::int32_t bottom = std::min({ record.height, height - record.y,
	                                       height - source_y });
	if (right <= left || bottom <= top) return;
	const std::int32_t copy_width = right - left;
	const std::int32_t copy_height = bottom - top;
	const std::int32_t destination_x = record.x + left;
	const std::int32_t destination_y = record.y + top;
	const std::int32_t source_left = source_x + left;
	const std::int32_t source_top = source_y + top;
	std::vector<std::uint8_t> temporary(static_cast<std::size_t>(copy_width) * copy_height);
	for (std::int32_t y = 0; y < copy_height; ++y)
		std::copy_n(pixels.data() + static_cast<std::size_t>(source_top + y) * pitch + source_left,
		            copy_width, temporary.data() + static_cast<std::size_t>(y) * copy_width);
	for (std::int32_t y = 0; y < copy_height; ++y)
		std::copy_n(temporary.data() + static_cast<std::size_t>(y) * copy_width,
		            copy_width, pixels.data() + static_cast<std::size_t>(destination_y + y) * pitch + destination_x);
}

} // namespace

int main()
{
	constexpr std::int32_t width = 16;
	constexpr std::int32_t height = 12;
	constexpr std::size_t pitch = 20;
	std::vector<std::uint8_t> pixels(pitch * height);
	for (std::size_t index = 0; index < pixels.size(); ++index)
		pixels[index] = static_cast<std::uint8_t>(index);
	std::vector<std::uint8_t> expected = pixels;

	Buffer commands;
	Require(commands.FillRect(-3, 2, 8, 5, 0xa5), "fill command append failed");
	Require(commands.CopyRect(4, 4, 9, 6, 1, 1), "copy command append failed");
	Require(commands.End(), "end command append failed");
	for (const Record &record : commands.records()) {
		if (record.opcode == 1) {
			const std::int32_t left = std::max(0, record.x);
			const std::int32_t top = std::max(0, record.y);
			const std::int32_t right = std::min(width, record.x + record.width);
			const std::int32_t bottom = std::min(height, record.y + record.height);
			for (std::int32_t y = top; y < bottom; ++y)
				std::fill(expected.begin() + static_cast<std::size_t>(y) * pitch + left,
				          expected.begin() + static_cast<std::size_t>(y) * pitch + right,
				          static_cast<std::uint8_t>(record.flags));
		} else if (record.opcode == 2) {
				ReferenceCopy(expected, pitch, width, height, record);
		}
	}

	SoftwareRenderer renderer(pixels, pitch, width, height);
	Require(renderer.Execute(commands.records()), "software command execution failed");
	Require(pixels == expected, "software command result differs from reference");

	std::array<Record, 1> unsupported {{ { 99, 0, 0, 0, 1, 1, 0, 0 } }};
	Require(!renderer.Execute(unsupported), "unsupported command was accepted");
	std::array<std::uint8_t, 1> short_pixels {};
	SoftwareRenderer invalid(short_pixels, 1, 2, 2);
	Require(!invalid.Execute(std::span<const Record> {}), "short target was accepted");
	// Malformed signed coordinates must clip/reject deterministically without
	// overflowing the software oracle used for command-path equality.
	std::vector<std::uint8_t> extreme_pixels(pitch * height, 0);
	std::vector<std::uint8_t> extreme_expected = extreme_pixels;
	const auto min_i32 = std::numeric_limits<std::int32_t>::min();
	const auto max_i32 = std::numeric_limits<std::int32_t>::max();
	std::array<Record, 5> extreme_records {{
		{ static_cast<std::uint32_t>(diablo::mister::command::Opcode::FillRect), 0x11,
		  min_i32, 0, max_i32, 1, 0, 0 },
		{ static_cast<std::uint32_t>(diablo::mister::command::Opcode::FillRect), 0x22,
		  max_i32, 0, max_i32, 1, 0, 0 },
		{ static_cast<std::uint32_t>(diablo::mister::command::Opcode::FillRect), 0x5a,
		  1, 1, max_i32, max_i32, 0, 0 },
		{ static_cast<std::uint32_t>(diablo::mister::command::Opcode::CopyRect), 0,
		  min_i32, max_i32, 1, 1, 0, 0 },
		{ static_cast<std::uint32_t>(diablo::mister::command::Opcode::End), 0,
		  0, 0, 0, 0, 0, 0 },
	}};
	for (std::int32_t y = 1; y < height; ++y)
		std::fill_n(extreme_expected.begin() + static_cast<std::size_t>(y) * pitch + 1,
		            width - 1, 0x5a);
	SoftwareRenderer extreme_renderer(extreme_pixels, pitch, width, height);
	Require(extreme_renderer.Execute(extreme_records), "extreme command records were rejected");
	Require(extreme_pixels == extreme_expected, "extreme command clipping overflowed or wrote incorrectly");

	Buffer full;
	for (std::size_t index = 0; index < Buffer::MaxRecords; ++index)
		Require(full.FillRect(0, 0, 1, 1, 0), "command capacity append failed");
	Require(!full.FillRect(0, 0, 1, 1, 0), "command capacity overflow was accepted");

	std::vector<std::uint8_t> shadow(640U * 480U, 0);
	std::vector<std::uint8_t> scene = shadow;
	std::array<std::uint8_t, 1> tiny_source {};
	Buffer invalid_pitch;
	Require(!BuildChangedRuns(invalid_pitch, tiny_source,
	                          std::numeric_limits<std::size_t>::max(), shadow, 0),
	        "changed-run builder accepted an overflowing source pitch");
	for (std::int32_t y = 20; y < 40; ++y)
		std::fill(scene.begin() + y * 640 + 30, scene.begin() + y * 640 + 90, 0x42);
	for (std::int32_t y = 60; y < 64; ++y)
		std::fill(scene.begin() + y * 640 + 100, scene.begin() + y * 640 + 160, 0x99);
	Buffer diff;
	Require(BuildChangedRuns(diff, scene, 640, shadow, 2), "scene diff build failed");
	Require(diff.size() == 2, "vertical scene runs were not coalesced");
	Require(diff.End(7), "scene diff fence append failed");
	std::vector<std::uint8_t> rendered = shadow;
	SoftwareRenderer diff_renderer(rendered, 640, 640, 480);
	Require(diff_renderer.Execute(diff.records()), "scene diff execution failed");
	Require(rendered == scene, "scene diff does not reconstruct the indexed surface");
	// Regression for an uninitialized previous-run lookup: a changed pixel on
	// row one at x=20 must not extend the unrelated row-zero run at x=10.
	std::vector<std::uint8_t> sparse = shadow;
	sparse[10] = 7;
	sparse[640 + 20] = 7;
	Buffer sparse_diff;
	Require(BuildChangedRuns(sparse_diff, sparse, 640, shadow, 0),
	        "sparse changed-run build failed");
	Require(sparse_diff.size() == 2, "unrelated sparse runs were coalesced");
	Require(sparse_diff.End(8), "sparse changed-run fence append failed");
	std::vector<std::uint8_t> sparse_rendered = shadow;
	SoftwareRenderer sparse_renderer(sparse_rendered, 640, 640, 480);
	Require(sparse_renderer.Execute(sparse_diff.records()), "sparse changed-run execution failed");
	Require(sparse_rendered == sparse, "sparse changed runs corrupt indexed pixels");
	// Keep a bounded deterministic differential set so changes to the run map
	// are checked beyond the minimal two-pixel regression.
	std::uint32_t seed = 0xC001D00DU;
	for (unsigned case_index = 0; case_index < 32; ++case_index) {
		std::vector<std::uint8_t> generated = shadow;
		for (unsigned change = 0; change < 96; ++change) {
			seed = seed * 1664525U + 1013904223U;
			const std::size_t pixel = seed % generated.size();
			generated[pixel] = static_cast<std::uint8_t>((seed >> 24U) | 1U);
		}
		Buffer generated_diff;
		Require(BuildChangedRuns(generated_diff, generated, 640, shadow, case_index % 3U),
		        "generated changed-run build failed");
		Require(generated_diff.End(case_index + 9U), "generated changed-run fence append failed");
		std::vector<std::uint8_t> generated_rendered = shadow;
		SoftwareRenderer generated_renderer(generated_rendered, 640, 640, 480);
		Require(generated_renderer.Execute(generated_diff.records()),
		        "generated changed-run execution failed");
		Require(generated_rendered == generated, "generated changed runs corrupt indexed pixels");
	}
	std::vector<std::uint8_t> noisy(640U * 480U);
	for (std::size_t index = 0; index < noisy.size(); ++index)
		noisy[index] = static_cast<std::uint8_t>(index);
	Buffer overflow;
	Require(!BuildChangedRuns(overflow, noisy, 640, shadow, 1),
	        "unrepresentable scene exceeded the command budget without fallback");
	std::cout << "software command renderer checks passed\n";
}
