// SPDX-License-Identifier: GPL-3.0-only
#include "mister_netplay.hpp"

#include <algorithm>
#include <cctype>
#include <cstdlib>

namespace devilution::mister_netplay {
namespace {

bool valid_code(const std::string &code)
{
	if (code.size() != 5) return false;
	return std::all_of(code.begin(), code.end(), [](unsigned char c) {
		return std::isalnum(c) != 0;
	});
}

} // namespace

Request read_request()
{
	Request request;
	const char *mode = std::getenv("DIABLO_MISTER_NETPLAY_MODE");
	const char *code = std::getenv("DIABLO_MISTER_NETPLAY_CODE");
	if (mode == nullptr || code == nullptr || !valid_code(code)) return request;
	request.code = code;
	std::transform(request.code.begin(), request.code.end(), request.code.begin(), [](unsigned char c) {
		return static_cast<char>(std::tolower(c));
	});
	if (std::string(mode) == "host") request.mode = Mode::Host;
	else if (std::string(mode) == "join") request.mode = Mode::Join;
	else request.code.clear();
	return request;
}

} // namespace devilution::mister_netplay
