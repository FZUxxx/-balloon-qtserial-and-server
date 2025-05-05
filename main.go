package main

import (
	"fmt"
	"net/http"

	"github.com/gin-gonic/gin"
)

var TOKEN string
//令牌生成与发送、json数据接收
func generateToken()string{
	return "sample_token_12345"
}

func getToken(c*gin.Context){
	if TOKEN==""{
		TOKEN=generateToken();
	}
	c.JSON(http.StatusOK,gin.H{
		"code":200,
		"token":TOKEN,
	})
}

func realTimeData(c*gin.Context){
	authHeader:=c.GetHeader("Authorization")
	if authHeader!=TOKEN{
		c.JSON(http.StatusOK,gin.H{
			"error":"useless"
		})
		return
	}

	var data map[string]interface{}
	if err:=c.BindJSON(&data);err!=nil{
		c.JSON(http.StatusBadRequest,gin.H{
			"error":"useless"
		})
	}
	// 打印收到的实时数据
	fmt.Printf("收到的实时数据: %+v\n", data)
	if err:=db.InsertDataToDB(data);err!=nil{
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": fmt.Sprintf("数据插入失败: %v", err),
		})
	}
	// 返回成功响应
	c.JSON(http.StatusOK, gin.H{
		"status":  "success",
		"message": "数据接收并插入成功",
	})
	
}
func main(){
	r:=gin.Default();
	r.GET("/token",getToken)
	r.POST("/real-time-data", realTimeData)
	
	/ 启动 HTTP 服务器
	fmt.Println("HTTP 服务器启动，监听端口 5000...")
	r.Run(":5000")
}