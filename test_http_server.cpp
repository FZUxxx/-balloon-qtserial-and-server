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
#include <json/json.h>  // ���� json �������� JSON ����
#include <sstream> //
using namespace std;

#define WEBROOT "."
#define DEFAULTINDEX "index.html"

// ȫ�����Ʊ���
string TOKEN = "";

// �������Ƶĺ���������Ը�����Ҫ�滻�������Ƶķ�ʽ��
string generate_token() {
	// ʾ���������ɷ�ʽ������ʹ�� UUID �������㷨
	return "sample_token_12345";
}

// ���� HTTP ����Ļص�����
void http_cb(struct evhttp_request *request, void *arg)
{
	cout << "http_cb" << endl;

	// ��ȡ URI �����󷽷�
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

	// ��ȡ����ͷ
	evkeyvalq *headers = evhttp_request_get_input_headers(request);
	cout << "====== headers ======" << endl;
	for (evkeyval *p = headers->tqh_first; p != NULL; p = p->next.tqe_next)
	{
		cout << p->key << ": " << p->value << endl;
	}

	// ��ȡ������
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

	// ����ͬ�� URI ����
	if (strcmp(uri, "/token") == 0 )
	{
		// �������ƻ�ȡ����
		if (TOKEN.empty()) {
			TOKEN = generate_token();  // ��������
		}

		// ���췵�ص� JSON ����
		Json::Value response_data;
		response_data["code"] = 200;
		response_data["token"] = TOKEN;

		// �������ͷ
		evkeyvalq *outhead = evhttp_request_get_output_headers(request);
		evhttp_add_header(outhead, "Content-Type", "application/json");

		// ������Ӧ
		evbuffer *outbuf = evhttp_request_get_output_buffer(request);
		string response_str = response_data.toStyledString();  // ʹ�� jsoncpp �⽫ JSON ����ת��Ϊ�ַ���
		evbuffer_add(outbuf, response_str.c_str(), response_str.length());
		evhttp_send_reply(request, HTTP_OK, "OK", outbuf);
	}
	else if (strcmp(uri, "/real-time-data") == 0 && cmdtype == "POST")
	{
		// ��ȡ Authorization ͷ��������
		const char* auth_header = evhttp_find_header(headers, "Authorization");
		if (auth_header == NULL || strcmp(auth_header, TOKEN.c_str()) != 0) {
			cout << "������Ч��ȱʧ��" << endl;
			evhttp_send_reply(request, HTTP_BADREQUEST, "Bad Request", 0);
			return;
		}

		// ���� POST �������е� JSON ����
		evbuffer *inbuf = evhttp_request_get_input_buffer(request);
		char buf[1024] = { 0 };
		int len = evbuffer_remove(inbuf, buf, sizeof(buf) - 1);
		buf[len] = '\0';

		std::istringstream iss(buf);
		// ʹ�� jsoncpp ����� JSON ����
		Json::CharReaderBuilder reader;
		Json::Value data;
		string errs;
		if (!Json::parseFromStream(reader, iss, &data, &errs)) // ʹ�� iss ������ buf
		{
			cout << "���� JSON ����ʧ��: " << errs << endl;
			evhttp_send_reply(request, HTTP_BADREQUEST, "Bad Request", 0);
			return;
		}

		// ��ӡ���յ��� JSON ����
		cout << "�յ���ʵʱ����: " << data.toStyledString() << endl;

		// ������Ӧ����
		Json::Value response_data;
		response_data["status"] = "success";
		response_data["message"] = "Data received successfully";

		// ���÷��ص� Content-Type
		evkeyvalq *outhead = evhttp_request_get_output_headers(request);
		evhttp_add_header(outhead, "Content-Type", "application/json");

		// ������Ӧ
		evbuffer *outbuf = evhttp_request_get_output_buffer(request);
		string response_str = response_data.toStyledString();  // ת��Ϊ JSON �ַ���
		evbuffer_add(outbuf, response_str.c_str(), response_str.length());
		evhttp_send_reply(request, HTTP_OK, "OK", outbuf);
	}
	else
	{
		// Ĭ�Ϸ��� 404 Not Found
		evhttp_send_reply(request, HTTP_NOTFOUND, "Not Found", 0);
	}
}

int main()
{
#ifdef _WIN32
	//��ʼ��socket��
	WSADATA wsa;
	WSAStartup(MAKEWORD(2, 2), &wsa);
#else
	// ���Թܵ��źţ��������ݸ��ѹرյ� socket
	if (signal(SIGPIPE, SIG_IGN) == SIG_ERR)
		return 1;
#endif

	std::cout << "test server!\n";

	// ���� libevent ��������
	event_base *base = event_base_new();
	if (base)
	{
		cout << "event_base_new success!" << endl;
	}

	// ���� HTTP ������
	evhttp *evh = evhttp_new(base);

	// �󶨶˿ں� IP
	if (evhttp_bind_socket(evh, "0.0.0.0", 5000) != 0)
	{
		cout << "evhttp_bind_socket failed!" << endl;
	}

	// ���ûص�����
	evhttp_set_gencb(evh, http_cb, 0);

	// �����¼�ѭ��
	if (base)
		event_base_dispatch(base);

	// ����
	if (base)
		event_base_free(base);
	if (evh)
		evhttp_free(evh);

#ifdef _WIN32
	WSACleanup();
#endif
	return 0;
}
