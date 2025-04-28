#include <event2/event.h>
#include <event2/listener.h>
#include <event2/http.h>
#include <event2/keyvalq_struct.h>
#include <event2/buffer.h>
#include <string.h>
#ifndef _WIN32
#include <signal.h>
#endif
#include <iostream>
#include <string>
#include <json/json.h>  // 引入 json 库来处理 JSON 数据
#include <sstream> //
using namespace std;

#define WEBROOT "."
#define DEFAULTINDEX "index.html"

// 全局令牌变量
string TOKEN = "";

// 生成令牌的函数（你可以根据需要替换生成令牌的方式）
string generate_token() {
	// 示例令牌生成方式，可以使用 UUID 或其他算法
	return "sample_token_12345";
}

// 处理 HTTP 请求的回调函数
void http_cb(struct evhttp_request *request, void *arg)
{
	cout << "http_cb" << endl;

	// 获取 URI 和请求方法
	const char *uri = evhttp_request_get_uri(request);
	cout << "uri: " << uri << endl;

	string cmdtype;
	switch (evhttp_request_get_command(request))
	{
	case EVHTTP_REQ_GET:
		cmdtype = "GET";
		break;
	case EVHTTP_REQ_POST:
		cmdtype = "POST";
		break;
	default:
		cmdtype = "UNKNOWN";
		break;
	}
	cout << "cmdtype: " << cmdtype << endl;

	// 获取请求头
	evkeyvalq *headers = evhttp_request_get_input_headers(request);
	cout << "====== headers ======" << endl;
	for (evkeyval *p = headers->tqh_first; p != NULL; p = p->next.tqe_next)
	{
		cout << p->key << ": " << p->value << endl;
	}

	// 获取请求体
	evbuffer *inbuf = evhttp_request_get_input_buffer(request);
	char buf[1024] = { 0 };
	cout << "======= Input data ======" << endl;
	while (evbuffer_get_length(inbuf))
	{
		int n = evbuffer_remove(inbuf, buf, sizeof(buf) - 1);
		if (n > 0)
		{
			buf[n] = '\0';
			cout << buf << endl;
		}
	}

	// 处理不同的 URI 请求
	if (strcmp(uri, "/token") == 0 )
	{
		// 处理令牌获取请求
		if (TOKEN.empty()) {
			TOKEN = generate_token();  // 生成令牌
		}

		// 构造返回的 JSON 数据
		Json::Value response_data;
		response_data["code"] = 200;
		response_data["token"] = TOKEN;

		// 构造输出头
		evkeyvalq *outhead = evhttp_request_get_output_headers(request);
		evhttp_add_header(outhead, "Content-Type", "application/json");

		// 发送响应
		evbuffer *outbuf = evhttp_request_get_output_buffer(request);
		string response_str = response_data.toStyledString();  // 使用 jsoncpp 库将 JSON 对象转换为字符串
		evbuffer_add(outbuf, response_str.c_str(), response_str.length());
		evhttp_send_reply(request, HTTP_OK, "OK", outbuf);
	}
	else if (strcmp(uri, "/real-time-data") == 0 && cmdtype == "POST")
	{
		// 获取 Authorization 头部的令牌
		const char* auth_header = evhttp_find_header(headers, "Authorization");
		if (auth_header == NULL || strcmp(auth_header, TOKEN.c_str()) != 0) {
			cout << "令牌无效或缺失！" << endl;
			evhttp_send_reply(request, HTTP_BADREQUEST, "Bad Request", 0);
			return;
		}

		// 解析 POST 请求体中的 JSON 数据
		evbuffer *inbuf = evhttp_request_get_input_buffer(request);
		char buf[1024] = { 0 };
		int len = evbuffer_remove(inbuf, buf, sizeof(buf) - 1);
		buf[len] = '\0';

		std::istringstream iss(buf);
		// 使用 jsoncpp 库解析 JSON 数据
		Json::CharReaderBuilder reader;
		Json::Value data;
		string errs;
		if (!Json::parseFromStream(reader, iss, &data, &errs)) // 使用 iss 而不是 buf
		{
			cout << "解析 JSON 数据失败: " << errs << endl;
			evhttp_send_reply(request, HTTP_BADREQUEST, "Bad Request", 0);
			return;
		}

		// 打印接收到的 JSON 数据
		cout << "收到的实时数据: " << data.toStyledString() << endl;

		// 构造响应数据
		Json::Value response_data;
		response_data["status"] = "success";
		response_data["message"] = "Data received successfully";

		// 设置返回的 Content-Type
		evkeyvalq *outhead = evhttp_request_get_output_headers(request);
		evhttp_add_header(outhead, "Content-Type", "application/json");

		// 发送响应
		evbuffer *outbuf = evhttp_request_get_output_buffer(request);
		string response_str = response_data.toStyledString();  // 转换为 JSON 字符串
		evbuffer_add(outbuf, response_str.c_str(), response_str.length());
		evhttp_send_reply(request, HTTP_OK, "OK", outbuf);
	}
	else
	{
		// 默认返回 404 Not Found
		evhttp_send_reply(request, HTTP_NOTFOUND, "Not Found", 0);
	}
}

int main()
{
#ifdef _WIN32
	//初始化socket库
	WSADATA wsa;
	WSAStartup(MAKEWORD(2, 2), &wsa);
#else
	// 忽略管道信号，发送数据给已关闭的 socket
	if (signal(SIGPIPE, SIG_IGN) == SIG_ERR)
		return 1;
#endif

	std::cout << "test server!\n";

	// 创建 libevent 的上下文
	event_base *base = event_base_new();
	if (base)
	{
		cout << "event_base_new success!" << endl;
	}

	// 创建 HTTP 服务器
	evhttp *evh = evhttp_new(base);

	// 绑定端口和 IP
	if (evhttp_bind_socket(evh, "0.0.0.0", 5000) != 0)
	{
		cout << "evhttp_bind_socket failed!" << endl;
	}

	// 设置回调函数
	evhttp_set_gencb(evh, http_cb, 0);

	// 启动事件循环
	if (base)
		event_base_dispatch(base);

	// 清理
	if (base)
		event_base_free(base);
	if (evh)
		evhttp_free(evh);

#ifdef _WIN32
	WSACleanup();
#endif
	return 0;
}
