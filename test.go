package main

import (
	"bytes"
	"testing"
	"net/http"
	"net/http/httptest"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
)

var r *gin.Engine

// 初始化函数，用于每个测试前初始化路由
func setup() {
	r = gin.Default()
	r.GET("/token", getToken)
	r.POST("/real-time-data", realTimeData)
}

// 测试获取令牌
func TestGetToken(t *testing.T) {
	// 设置路由
	setup()

	// 使用 httptest 创建一个请求
	req, _ := http.NewRequest("GET", "/token", nil)
	w := httptest.NewRecorder()

	// 执行请求
	r.ServeHTTP(w, req)

	// 检查返回的状态码是否为 200
	assert.Equal(t, http.StatusOK, w.Code)

	// 检查返回的令牌内容
	expectedToken := `"token":"sample_token_12345"`
	assert.Contains(t, w.Body.String(), expectedToken)
}

// 测试实时数据接口，令牌有效
func TestRealTimeDataValidToken(t *testing.T) {
	// 设置路由
	setup()

	// 先获取令牌
	tokenReq, _ := http.NewRequest("GET", "/token", nil)
	tokenResp := httptest.NewRecorder()
	r.ServeHTTP(tokenResp, tokenReq)
	// 提取令牌
	token := tokenResp.Body.String()

	// 构造带令牌的 POST 请求
	data := `{
		"taskId": "test",
		"status": "1",
		"longitude": 12.34,
		"latitude": 56.78,
		"time": "2025-02-27T12:00:00Z"
	}`

	req, _ := http.NewRequest("POST", "/real-time-data", bytes.NewBuffer([]byte(data)))
	req.Header.Set("Authorization", "sample_token_12345") // 设置正确的令牌
	w := httptest.NewRecorder()

	// 执行请求
	r.ServeHTTP(w, req)

	// 检查返回的状态码
	assert.Equal(t, http.StatusOK, w.Code)

	// 检查响应内容
	expectedMessage := `"message":"数据接收成功"`
	assert.Contains(t, w.Body.String(), expectedMessage)
}

// 测试实时数据接口，令牌无效
func TestRealTimeDataInvalidToken(t *testing.T) {
	// 设置路由
	setup()

	// 构造带无效令牌的 POST 请求
	data := `{
		"taskId": "test",
		"status": "1",
		"longitude": 12.34,
		"latitude": 56.78,
		"time": "2025-02-27T12:00:00Z"
	}`

	req, _ := http.NewRequest("POST", "/real-time-data", bytes.NewBuffer([]byte(data)))
	req.Header.Set("Authorization", "invalid_token") // 设置无效的令牌
	w := httptest.NewRecorder()

	// 执行请求
	r.ServeHTTP(w, req)

	// 检查返回的状态码
	assert.Equal(t, http.StatusBadRequest, w.Code)

	// 检查错误信息
	expectedError := `"error":"令牌无效或缺失"`
	assert.Contains(t, w.Body.String(), expectedError)
}

// 测试实时数据接口，缺失令牌
func TestRealTimeDataMissingToken(t *testing.T) {
	// 设置路由
	setup()

	// 构造没有令牌的 POST 请求
	data := `{
		"taskId": "test",
		"status": "1",
		"longitude": 12.34,
		"latitude": 56.78,
		"time": "2025-02-27T12:00:00Z"
	}`

	req, _ := http.NewRequest("POST", "/real-time-data", bytes.NewBuffer([]byte(data)))
	w := httptest.NewRecorder()

	// 执行请求
	r.ServeHTTP(w, req)

	// 检查返回的状态码
	assert.Equal(t, http.StatusBadRequest, w.Code)

	// 检查错误信息
	expectedError := `"error":"令牌无效或缺失"`
	assert.Contains(t, w.Body.String(), expectedError)
}
