// Exercise the pinned engine's real providers without loading game assets.
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include <array>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#ifdef _WIN32
#define ADD_EXPORTS
#endif
#include <ZeroTierSockets.h>
#include "dvlnet/abstract_net.h"
#include "dvlnet/zerotier_native.h"
#include "player.h"
#include "utils/paths.h"

int main(int argc, char **argv)
{
	if (argc != 5 || (std::strcmp(argv[1], "tcp") != 0 && std::strcmp(argv[1], "zt") != 0 && std::strcmp(argv[1], "zt-public") != 0)
	    || (std::strcmp(argv[2], "host") != 0 && std::strcmp(argv[2], "join") != 0)) {
		std::fprintf(stderr, "usage: netplay-peer tcp|zt|zt-public host|join address-or-game-id config-directory\n");
		return 2;
	}
	SDL_SetMainReady();
	if (SDL_Init(SDL_INIT_TIMER) != 0) return 2;
	using namespace devilution;
	Players.resize(MAX_PLRS);
	const bool zt = std::strcmp(argv[1], "tcp") != 0;
	const bool host = std::strcmp(argv[2], "host") == 0;
	paths::SetConfigPath(argv[4]);
	if (zt) {
		// Production uses libzt's default port. Tests that run two nodes on one
		// machine can opt into separate ports with DVL_NETPLAY_PORT.
		if (const char *port = std::getenv("DVL_NETPLAY_PORT"); port != nullptr) {
			char *end = nullptr;
			const unsigned long value = std::strtoul(port, &end, 10);
			if (*port == '\0' || *end != '\0' || value > 65535 || zts_init_set_port(static_cast<unsigned short>(value)) != ZTS_ERR_OK)
				return 3;
		}
	}
	auto peer = net::abstract_net::MakeNet(zt ? SELCONN_ZT : SELCONN_TCP);
	if (zt) {
		const auto start = SDL_GetTicks();
		while (!net::zerotier_network_ready() && SDL_GetTicks() - start < 60000) {
			SDL_Delay(10);
		}
		if (!net::zerotier_network_ready()) {
			std::fprintf(stderr, "ZeroTier network not ready within 60 seconds\n");
			return 3;
		}
	}
	if (std::strcmp(argv[1], "zt-public") == 0)
		peer->clear_password();
	else
		peer->setup_password("netplay-regression");
	GameData game {};
	game.size = sizeof(GameData);
	net::buffer_t info(sizeof(game));
	std::memcpy(info.data(), &game, sizeof(game));
	peer->setup_gameinfo(std::move(info));
	const int id = host ? peer->create(argv[3]) : peer->join(argv[3]);
	if (id < 0) {
		std::fprintf(stderr, "join/create failed: %s\n", SDL_GetError());
		for (const auto &gameInfo : peer->get_gamelist())
			std::fprintf(stderr, "discovered game name=%s\n", gameInfo.name.c_str());
		return 4;
	}
	// The real game assigns this immediately after the provider join. Keep the
	// standalone exchange harness in the same state so player 0 is not treated
	// as the client itself when it sends its first message.
	MyPlayerId = static_cast<size_t>(id);
	std::printf("READY player=%d\n", id);
	std::fflush(stdout);
	// Valid frames below the 65535-byte framing limit. This burst exceeds
	// socket buffers to expose overlapping composed async_write calls.
	constexpr unsigned PacketCount = 128;
	constexpr unsigned PacketSize = 60000;
	constexpr unsigned TurnCount = 32;
	unsigned received = 0;
	unsigned turns = 0;
	bool sent = false;
	bool sentTurns = false;
	uint32_t completed = 0;
	const auto start = SDL_GetTicks();
	while (SDL_GetTicks() - start < 120000) {
		if (!host && !sent) {
			for (unsigned i = 0; i < PacketCount; ++i) {
				std::array<unsigned char, PacketSize> request;
				for (unsigned j = 0; j < PacketSize; ++j)
					request[j] = static_cast<unsigned char>((i * 17 + j * 31) % 251);
				std::memcpy(request.data(), &i, sizeof(i));
				if (!peer->SNetSendMessage(0, request.data(), request.size())) return 5;
			}
			sent = true;
		}
		uint8_t sender;
		void *data;
		uint32_t size;
		while (peer->SNetReceiveMessage(&sender, &data, &size)) {
			unsigned sequence = 0;
			if (size != PacketSize || received >= PacketCount || sender != (host ? 1 : 0)) return 5;
			std::memcpy(&sequence, data, sizeof(sequence));
			if (sequence != received) {
				std::fprintf(stderr, "packet order: expected %u got %u\n", received, sequence);
				return 5;
			}
			for (unsigned j = sizeof(sequence); j < PacketSize; ++j)
				if (static_cast<unsigned char *>(data)[j] != (sequence * 17 + j * 31) % 251) return 5;
			++received;
			if (host && !peer->SNetSendMessage(sender, data, size)) return 5;
		}
		if (!sentTurns && (!host || received != 0)) {
			for (unsigned i = 0; i < TurnCount; ++i) {
				int32_t value = id * 1000 + i;
				if (!peer->SNetSendTurn(reinterpret_cast<char *>(&value), sizeof(value))) return 7;
			}
			sentTurns = true;
		}
		if (sentTurns && turns < TurnCount) {
			std::array<char *, MAX_PLRS> turnData {};
			std::array<size_t, MAX_PLRS> turnSize {};
			std::array<uint32_t, MAX_PLRS> status {};
			if (peer->SNetReceiveTurns(turnData.data(), turnSize.data(), status.data())) {
				for (unsigned player = 0; player < 2; ++player) {
					int32_t value;
					if (!(status[player] & PS_TURN_ARRIVED) || turnSize[player] != sizeof(value)) return 7;
					std::memcpy(&value, turnData[player], sizeof(value));
					if (value != static_cast<int32_t>(player * 1000 + turns)) return 7;
				}
				++turns;
			}
		}
		if (received == PacketCount && turns == TurnCount) {
			if (!completed) completed = SDL_GetTicks();
			// Keep both peers alive while the other consumes its final turns.
			if (SDL_GetTicks() - completed > 3000) {
				std::printf("PASS provider=%s player=%d packets=%u bytes=%u turns=%u\n", argv[1], id, received, received * PacketSize, turns);
				std::fflush(stdout);
				return 0;
			}
		}
		SDL_Delay(10);
	}
	std::fprintf(stderr, "exchange timed out: packets=%u turns=%u\n", received, turns);
	return 6;
}
