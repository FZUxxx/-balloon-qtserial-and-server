test_http_server:test_http_server.cpp
	g++ test_http_server.cpp -o test_http_server -L/usr/local/lib -I/usr/include/jsoncpp/ -levent -ljsoncpp
	./$@
clean:
	rm -rf test_http_server
	rm -rf *.o

