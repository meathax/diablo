"""Generate guarded 1.5.5 networking fixes without editing the pinned checkout."""
import hashlib
from pathlib import Path
import sys

HASHES = {
    "base_protocol.h": "7fc7733f0209f916c3bd1435703409ceb33d4214c94c106bc0703932cb1479b1",
    "protocol_zt.h": "51f7d8842674e8af52991de14988d83722e0c9ebf0c6183d4128dca4ed086e34",
    "protocol_zt.cpp": "640852ebddb77dd9df748fded21fb32bd928e85e0d77d2d955132828c21e7659",
    "zerotier_native.h": "81482c8ccd7ae914cdde0999596bccc5ae3a89c325eefca7d49f0b0cdee291d3",
    "zerotier_native.cpp": "d4aaac27e0e9a17132d4bda85bfb42e057b450f3a93c9700584b1720ce63072e",
    "zerotier_lwip.cpp": "a02a336f3522e7f67c60b2c8ec9ad2e7406768ce63180fd4643cc5609a2e97c0",
    "tcp_client.h": "325279541d6f4c36436c2c52de1fe8ef3e71eed10fa2e75744d5cb53a14de6ed",
    "tcp_client.cpp": "7cb5624ccf08ad2a652f2c1f7d8a7d6d9bb82c1b0d02003a2ef9933e8c9cfd23",
    "tcp_server.h": "914866ed6e6978cb9f715bf14587ca1d9fa2cb26cd8cd1ace578368614490313",
    "tcp_server.cpp": "36c0049d35c53142c134afbde9e216b6cee3d5430a1b2850fb09ebbcda308211",
}


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected exactly one netplay patch anchor: {old[:80]!r}")
    return text.replace(old, new)


def patch(name, text):
    if name == "base_protocol.h":
        text = replace_once(text, """	if (!proto.network_online())
		return false;""", """	if (!proto.peers_ready())
		return false;""")
        text = replace_once(text, """	// wait for ZeroTier for 5 seconds
	for (auto i = 0; i < 500; ++i) {""", """	// allow ZeroTier transport to settle before game setup (15 seconds)
	for (auto i = 0; i < 1500; ++i) {""")
        text = replace_once(text, """	// wait for peer for 5 seconds
	for (auto i = 0; i < 500; ++i) {""", """	// allow ZeroTier peer discovery to settle (15 seconds)
	for (auto i = 0; i < 1500; ++i) {""")
        text = replace_once(text, """bool base_protocol<P>::send_info_request()
{
	if (!proto.peers_ready())
		return false;
	auto pkt = pktfty->make_packet<PT_INFO_REQUEST>(PLR_BROADCAST, PLR_MASTER);
	proto.send_oob_mc(pkt->Data());
	return true;
}""", """bool base_protocol<P>::send_info_request()
{
	if (!proto.peers_ready())
		return false;
	auto pkt = pktfty->make_packet<PT_INFO_REQUEST>(PLR_BROADCAST, PLR_MASTER);
	proto.send_oob_mc(pkt->Data());
	return true;
}""")
        text = replace_once(text,
            "\t\t\t\tproto.send_oob(sender, reply->Data());",
            """\t\t\t\tproto.send_oob(sender, reply->Data());
\t\t\t\t// A multicast fallback covers libzt peers whose unicast neighbor
\t\t\t\t// cache is not populated yet during discovery.
\t\t\t\tproto.send_oob_mc(reply->Data());""")
        return text
    if name == "protocol_zt.h":
        text = replace_once(text, "	bool network_online();", """	bool network_online();
	bool peers_ready();""")
        return replace_once(text, "		int fd = -1;", """		int fd = -1;
		bool connecting = false;""")
    if name == "protocol_zt.cpp":
        anchor = """bool protocol_zt::send(const endpoint &peer, const buffer_t &data)
"""
        text = replace_once(text, anchor, """bool protocol_zt::peers_ready()
{
	return network_online() && zerotier_peers_ready();
}

""" + anchor)
        text = replace_once(text, """\tlwip_sendto(fd_udp, data.data(), data.size(), 0, (const struct sockaddr *)&in6, sizeof(in6));
\treturn true;""", """\tconst auto sent = lwip_sendto(fd_udp, data.data(), data.size(), 0, (const struct sockaddr *)&in6, sizeof(in6));
\tif (sent < 0)
\t\treturn false;
\tif (static_cast<size_t>(sent) != data.size())
\t\treturn false;
\treturn true;""")
        text = replace_once(text,
            """bool protocol_zt::send_queued_peer(const endpoint &peer)
{
\tif (peer_list[peer].fd == -1) {
\t\tpeer_list[peer].fd = lwip_socket(AF_INET6, SOCK_STREAM, 0);
\t\tset_nodelay(peer_list[peer].fd);
\t\tset_nonblock(peer_list[peer].fd);
\t\tstruct sockaddr_in6 in6 {
\t\t};
\t\tin6.sin6_port = htons(default_port);
\t\tin6.sin6_family = AF_INET6;
\t\tstd::copy(peer.addr.begin(), peer.addr.end(), in6.sin6_addr.s6_addr);
\t\tlwip_connect(peer_list[peer].fd, (const struct sockaddr *)&in6, sizeof(in6));
\t}
\twhile (!peer_list[peer].send_queue.empty()) {
\t\tauto len = peer_list[peer].send_queue.front().size();
\t\tauto r = lwip_send(peer_list[peer].fd, peer_list[peer].send_queue.front().data(), len, 0);
\t\tif (r < 0) {
\t\t\t// handle error
\t\t\treturn false;
\t\t}
\t\tif (decltype(len)(r) < len) {
\t\t\t// partial send
\t\t\tauto it = peer_list[peer].send_queue.front().begin();
\t\t\tpeer_list[peer].send_queue.front().erase(it, it + r);
\t\t\treturn true;
\t\t}
\t\tif (decltype(len)(r) == len) {
\t\t\tpeer_list[peer].send_queue.pop_front();
\t\t} else {
\t\t\tthrow protocol_exception();
\t\t}
\t}
\treturn true;
}""",
            """bool protocol_zt::send_queued_peer(const endpoint &peer)
{
\tauto &state = peer_list[peer];
\tif (state.fd == -1) {
\t\tstate.fd = lwip_socket(AF_INET6, SOCK_STREAM, 0);
\t\tif (state.fd < 0)
\t\t\treturn false;
\t\tset_nodelay(state.fd);
\t\tset_nonblock(state.fd);
\t\tstruct sockaddr_in6 in6 {
\t\t};
\t\tin6.sin6_port = htons(default_port);
\t\tin6.sin6_family = AF_INET6;
\t\tstd::copy(peer.addr.begin(), peer.addr.end(), in6.sin6_addr.s6_addr);
\t\tconst auto connect_result = lwip_connect(state.fd, (const struct sockaddr *)&in6, sizeof(in6));
\t\tif (connect_result < 0) {
\t\t\tconst auto connect_error = errno;
\t\t\tif (connect_error != EINPROGRESS && connect_error != EALREADY && connect_error != EWOULDBLOCK) {
\t\t\t\tlwip_close(state.fd);
\t\t\t\tstate.fd = -1;
\t\t\t\treturn false;
\t\t\t}
\t\t\tstate.connecting = true;
\t\t}
\t}
\tif (state.connecting) {
\t\tstruct pollfd poll_fd {
\t\t};
\t\tpoll_fd.fd = state.fd;
\t\tpoll_fd.events = POLLOUT;
\t\tconst auto poll_result = lwip_poll(&poll_fd, 1, 0);
\t\tif (poll_result < 0) {
\t\t\tif (errno == EAGAIN || errno == EWOULDBLOCK)
\t\t\t\treturn true;
\t\t\tlwip_close(state.fd);
\t\t\tstate.fd = -1;
\t\t\tstate.connecting = false;
\t\t\treturn false;
\t\t}
\t\tif (poll_result == 0)
\t\t\treturn true;
\t\tif ((poll_fd.revents & (POLLERR | POLLHUP | POLLNVAL)) != 0) {
\t\t\tlwip_close(state.fd);
\t\t\tstate.fd = -1;
\t\t\tstate.connecting = false;
\t\t\treturn false;
\t\t}
\t\tif ((poll_fd.revents & POLLOUT) == 0)
\t\t\treturn true;
\t\tstate.connecting = false;
\t}
\twhile (!state.send_queue.empty()) {
\t\tauto len = state.send_queue.front().size();
\t\tauto r = lwip_send(state.fd, state.send_queue.front().data(), len, 0);
\t\tif (r < 0) {
\t\t\treturn errno == EAGAIN || errno == EWOULDBLOCK;
\t\t}
\t\tif (decltype(len)(r) < len) {
\t\t\tauto it = state.send_queue.front().begin();
\t\t\tstate.send_queue.front().erase(it, it + r);
\t\t\treturn true;
\t\t}
\t\tif (decltype(len)(r) == len)
\t\t\tstate.send_queue.pop_front();
\t\telse
\t\t\tthrow protocol_exception();
\t}
\treturn true;
}""")
        text = replace_once(text,
            """\tauto len = lwip_recvfrom(fd_udp, buf, sizeof(buf), 0, (struct sockaddr *)&in6, &addrlen);
\tif (len < 0)
\t\treturn false;
\tbuffer_t data(buf, buf + len);""",
            """\tauto len = lwip_recvfrom(fd_udp, buf, sizeof(buf), 0, (struct sockaddr *)&in6, &addrlen);
\tif (len < 0)
\t\treturn false;
\tbuffer_t data(buf, buf + len);
""")
        text = replace_once(text,
            """\t\tif (len >= 0) {
\t\t\tpeer_list[peer].recv_queue.Write(buffer_t(buf, buf + len));
\t\t} else {
\t\t\treturn errno == EAGAIN || errno == EWOULDBLOCK;
\t\t}""",
            """\t\tif (len > 0) {
\t\t\tpeer_list[peer].recv_queue.Write(buffer_t(buf, buf + len));
\t\t} else if (len == 0) {
\t\t\treturn false;
\t\t} else {
\t\t\treturn errno == EAGAIN || errno == EWOULDBLOCK;
\t\t}""")
        text = replace_once(text,
            """\t\tauto newfd = lwip_accept(fd_tcp, (struct sockaddr *)&in6, &addrlen);
\t\tif (newfd < 0)
\t\t\tbreak;""",
            """\t\tauto newfd = lwip_accept(fd_tcp, (struct sockaddr *)&in6, &addrlen);
\t\tif (newfd < 0)
\t\t\tbreak;
""")
        return text
    if name == "zerotier_native.h":
        text = replace_once(text, "bool zerotier_network_ready();",
                            """bool zerotier_network_ready();
bool zerotier_peers_ready();""")
        return text
    if name == "zerotier_native.cpp":
        text = replace_once(text, """		if (!zt_joined) {
			zts_net_join(ZtNetwork);
			zt_joined = true;
		}""", """		if (!zt_joined) {
			const auto result = zts_net_join(ZtNetwork);
			if (result == ZTS_ERR_OK)
				zt_joined = true;
			else
				LogError("ZeroTier: failed to join network: {}", result);
		}""")
        text = replace_once(text, """	} else if (msg->event_code == ZTS_EVENT_NODE_OFFLINE) {
		Log("ZeroTier: ZTS_EVENT_NODE_OFFLINE");
		zt_node_online = false;
	}""", """	} else if (msg->event_code == ZTS_EVENT_NODE_OFFLINE) {
		Log("ZeroTier: ZTS_EVENT_NODE_OFFLINE");
		zt_node_online = false;
		zt_network_ready = false;
		zt_joined = false;
		zt_peers_ready = 0;
		zt_ip6_configured = false;
	}""")
        text = replace_once(text, "#include <atomic>", """#include <algorithm>
#include <atomic>

#ifdef _WIN32
#define ADD_EXPORTS
#endif""")
        text = replace_once(text,
            "static std::atomic_bool zt_joined(false);",
            """static std::atomic_bool zt_joined(false);
static std::atomic_bool zt_started(false);
static std::atomic_uint zt_peers_ready(0);
static std::atomic_bool zt_ip6_configured(false);""")
        text = replace_once(text,
            "		zt_ip6setup();\n		zt_network_ready = true;",
            """		// The callback runs after libzt has installed the lwIP netif.
		// Repeat the join even if readiness was observed through the API first.
		zt_ip6setup();
		zt_ip6_configured = true;
		zt_network_ready = true;
		zt_peers_ready = SDL_GetTicks();""")
        text = replace_once(text, """	} else if (msg->event_code == ZTS_EVENT_ADDR_ADDED_IP6) {
		print_ip6_addr(&(msg->addr->addr));
	}""", """	} else if (msg->event_code == ZTS_EVENT_NETWORK_DOWN) {
		zt_network_ready = false;
		zt_peers_ready = 0;
		zt_ip6_configured = false;
	} else if (msg->event_code == ZTS_EVENT_ADDR_ADDED_IP6) {
		print_ip6_addr(&(msg->addr->addr));
	}""")
        text = replace_once(text, """void zerotier_network_start()
{
	std::string configPath = paths::ConfigPath();
#ifdef DVL_ZT_SYMLINK
	configPath = ToZTCompliantPath(configPath);
#endif
	std::string ztpath = configPath + "zerotier";
	zts_init_from_storage(ztpath.c_str());
	zts_init_set_event_handler(&Callback);
	zts_node_start();
}""", """void zerotier_network_start()
{
	if (zt_started.exchange(true))
		return;
	std::string configPath = paths::ConfigPath();
#ifdef DVL_ZT_SYMLINK
	configPath = ToZTCompliantPath(configPath);
#endif
	std::string ztpath = configPath + "zerotier";
	const auto storage_result = zts_init_from_storage(ztpath.c_str());
	const auto handler_result = zts_init_set_event_handler(&Callback);
	const auto start_result = zts_node_start();
	if (storage_result != ZTS_ERR_OK || handler_result != ZTS_ERR_OK || start_result != ZTS_ERR_OK) {
		LogError("ZeroTier: startup failed (storage={}, handler={}, node={})", storage_result, handler_result, start_result);
		zt_started = false;
	}
}""")
        return replace_once(text, """bool zerotier_network_ready()
{
	return zt_network_ready && zt_node_online;
}""", """bool zerotier_network_ready()
{
	// A cached network can be usable before libzt publishes NODE_ONLINE. The
	// network status, assigned address, and transport flag are the authoritative
	// indicators that the lwIP socket layer can send traffic.
	if (zts_net_get_status(ZtNetwork) != ZTS_NETWORK_STATUS_OK ||
	    zts_addr_is_assigned(ZtNetwork, ZTS_AF_INET6) != 1 || zts_net_transport_is_ready(ZtNetwork) != 1)
		return false;
	zt_node_online = true;
	zt_joined = true;
	if (!zt_ip6_configured.exchange(true))
		zt_ip6setup();
	if (!zt_network_ready.exchange(true))
		zt_peers_ready = SDL_GetTicks();
	return true;
}

bool zerotier_peers_ready()
{
	return zerotier_network_ready() && SDL_GetTicks() - zt_peers_ready.load() >= 5000;
}""")
    if name == "zerotier_lwip.cpp":
        return replace_once(text,
            """\tmld6_joingroup(IP6_ADDR_ANY6, &mcaddr);""",
            """\t(void)mld6_joingroup(IP6_ADDR_ANY6, &mcaddr);""")
    if name == "tcp_client.h":
        text = replace_once(text, "#include <memory>", """#include <deque>
#include <memory>""")
        text = replace_once(text, "	frame_queue recv_queue;",
                            """	frame_queue recv_queue;
	std::deque<std::shared_ptr<buffer_t>> send_queue;""")
        return replace_once(text, "	void StartReceive();", """	void StartReceive();
	void StartSend();""")
    if name == "tcp_server.h":
        text = replace_once(text, "#include <memory>", """#include <deque>
#include <memory>""")
        text = replace_once(text, "		frame_queue recv_queue;",
                            """		frame_queue recv_queue;
		std::deque<std::shared_ptr<buffer_t>> send_queue;""")
        return replace_once(text, "	void StartSend(const scc &con, packet &pkt);",
                            """	void StartSend(const scc &con, packet &pkt);
	void StartQueuedSend(const scc &con);""")
    if name == "tcp_client.cpp":
        text = replace_once(text, "	// empty for now", """	if (error) {
		send_queue.clear();
		asio::error_code ignored;
		sock.close(ignored);
		return;
	}
	send_queue.pop_front();
	if (!send_queue.empty())
		StartSend();""")
        return replace_once(text, """	auto frame = std::make_unique<buffer_t>(frame_queue::MakeFrame(pkt.Data()));
	auto buf = asio::buffer(*frame);
	asio::async_write(sock, buf, [this, frame = std::move(frame)]""", """	if (!sock.is_open())
		return;
	send_queue.push_back(std::make_shared<buffer_t>(frame_queue::MakeFrame(pkt.Data())));
	if (send_queue.size() == 1)
		StartSend();
}

void tcp_client::StartSend()
{
	// Retain the active frame through completion, including cancellation.
	auto frame = send_queue.front();
	auto buf = asio::buffer(*frame);
	asio::async_write(sock, buf, [this, frame]""")
    if name == "tcp_server.cpp":
        text = replace_once(text,
            """	if (plr == PLR_BROADCAST) {
		return;
	}
	connections[plr] = nullptr;""",
            """	if (plr == PLR_BROADCAST || connections[plr] != con) {
		return;
	}
	connections[plr] = nullptr;""")
        text = replace_once(text, "	// empty for now", """	if (ec) {
		con->send_queue.clear();
		if (con->socket.is_open())
			DropConnection(con);
		return;
	}
	con->send_queue.pop_front();
	if (!con->send_queue.empty())
		StartQueuedSend(con);""")
        return replace_once(text, """	auto frame = std::make_unique<buffer_t>(frame_queue::MakeFrame(pkt.Data()));
	auto buf = asio::buffer(*frame);
	asio::async_write(con->socket, buf,
	    [this, con, frame = std::move(frame)]""", """	if (!con->socket.is_open())
		return;
	con->send_queue.push_back(std::make_shared<buffer_t>(frame_queue::MakeFrame(pkt.Data())));
	if (con->send_queue.size() == 1)
		StartQueuedSend(con);
}

void tcp_server::StartQueuedSend(const scc &con)
{
	auto frame = con->send_queue.front();
	auto buf = asio::buffer(*frame);
	asio::async_write(con->socket, buf,
	    [this, con, frame]""")
    raise ValueError(f"Unsupported netplay overlay file: {name}")


def generate(source, output):
    generated = {}
    for name, digest in HASHES.items():
        raw = (source / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"Unexpected pinned 1.5.5 networking source: {name}")
        generated[name] = patch(name, raw.decode().replace("\r\n", "\n"))
    output.mkdir(parents=True, exist_ok=True)
    for name, text in generated.items():
        target = output / name
        if not target.exists() or target.read_text() != text:
            target.write_text(text, newline="\n")


if __name__ == "__main__":
    generate(Path(sys.argv[1]), Path(sys.argv[2]))
