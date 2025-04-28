import sys
import time
from datetime import datetime

import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout,
                             QHBoxLayout, QWidget, QLabel, QComboBox, QTextEdit, QGridLayout)
from PyQt5.QtCore import QTimer, QTime
import matplotlib.pyplot as plt
from folium import Map
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWebEngineWidgets import QWebEngineView
import io
import folium
import requests
import xlwt
import threading
from PyQt5.QtCore import pyqtSignal, QObject
from requests import RequestException
from requests.exceptions import RequestException, ConnectionError, Timeout, HTTPError
from threading import Lock
from PyQt5.QtGui import QFont

class DataProcessor(QObject):
    dataUpdated = pyqtSignal(list)
    saveexcel = pyqtSignal(list)


class SerialReader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

        self.serial = None
        self.is_reading = False  # 控制线程状态

        self.latitudes = []
        self.longitudes = []
        self.altitudes = []
        self.discharge_volume = []
        self.gas_volume = []
        self.times = []
        self.start_time = QTime.currentTime()
        self.token = ""  # 新增变量用于存储token
        self.update_timer = QTimer()  # 创建一个定时器，用于更新地图和绘图
        self.update_timer.timeout.connect(self.update_all)  # 连接定时器的 timeout 信号到 update_all 方法
        self.current_data = []  # 用于存储当前数据的实例变量
        self.dataProcessor = DataProcessor()  # 初始化 DataProcessor
        self.dataProcessor.dataUpdated.connect(self.update_all)  # 连接信号
        self.token_timer = QTimer()  # 创建一个定时器，用于定时获取令牌
        self.token_timer.timeout.connect(self.get_token)  # 连接定时器的 timeout 信号到 get_token 方法
        self.token_url = ""  # 存储获取令牌的URL
        self.real_time_url = ""
        self.data_updated = False  # 新增标志位
        self.data_count = 0  # 当前写入的数据量
        self.save_threshold = 100  # 自动保存的阈值
        font = QFont()
        font.setFamily('SimSun')  # 设置字体为宋体，这是一种常用的中文字体
        font.setPointSize(10)  # 设置字体大小
        self.data_text_edit.setFont(font)

    def initUI(self):
        self.setWindowTitle('浮空器控制平台')
        # URL输入框
        self.token_url_label = QLabel('获取令牌URL:')
        self.token_url_edit = QTextEdit()
        self.token_url_edit.setMaximumHeight(30)

        self.real_time_url_label = QLabel('发送实时数据URL:')
        self.real_time_url_edit = QTextEdit()
        self.real_time_url_edit.setMaximumHeight(30)
        # 串口设置相关控件
        self.port_label = QLabel('串口:')
        self.baudrate_label = QLabel('波特率:')
        self.port_box = QComboBox()
        self.baudrate_box = QComboBox()
        self.baudrate_box.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.scan_ports()

        # 发送数据
        self.ballast_send_label = QLabel('抛物量,排气量:')
        self.ballast_send_edit = QTextEdit()
        self.ballast_send_edit.setMaximumHeight(30)

        self.send_button = QPushButton('发送数据')
        self.send_button.clicked.connect(self.send_serial_data)

        # 操作按钮
        self.start_button = QPushButton('开始读取')
        self.stop_button = QPushButton('停止读取')
        self.start_button.clicked.connect(self.start_reading)
        self.stop_button.clicked.connect(self.stop_reading)

        self.rc_task_status_label = QLabel('RC任务状态: 待命')
        self.cutter_status_label = QLabel('切断器状态: 未激活')
        self.battery_voltage_status_label = QLabel('电池电压状态: 正常')
        self.timeout_status_label = QLabel('超时状态: 未超时')
        self.ultra_high_status_label = QLabel('超高状态: 正常')
        self.ultra_fence_status_label = QLabel('超围栏状态: 正常')
        self.active_cutting_status_label = QLabel('主动切断状态: 未切断')

        # 飞行参数模块
        self.horizontal_speed_label = QLabel('水平速度: 0 m/s')
        self.climbing_speed_label = QLabel('上升速度: 0 m/s')
        self.z_acceleration_label = QLabel('z加速度: 0 m/s^2')
        self.longitude_label = QLabel('经度: 0.0')
        self.latitude_label = QLabel('纬度: 0.0')
        self.fusion_altitude_label = QLabel('融合高度: 0 米')
        self.pressure_altitude_label = QLabel('气压高度: 0 米')
        self.gps_altitude_label = QLabel('GPS高度: 0 米')
        self.target_altitude_label = QLabel('目标平飘高度: 0 米')
        self.pt100_temperature_label = QLabel('PT100温度: 0 度')
        self.board_temperature_label = QLabel('板上温度: 0 度')
        self.battery_temperature_label = QLabel('电池温度: 0 度')
        self.battery_voltage_label = QLabel('GPS2高度: 0 米')
        self.capacitor_voltage_label = QLabel('电容电压: 0 V')
        self.venting_time_label = QLabel('排气时间: 0 秒')
        self.ballast_quantity_label = QLabel('抛物量: 0 个')
        self.message_label = QLabel('北斗上发消息量:0')
        self.time_label = QLabel('时间:0:00')
        # 地图显示窗口
        self.map_view = QWebEngineView()

        # 高度曲线显示
        self.canvas = FigureCanvas(plt.Figure())
        self.ax_altitude = self.canvas.figure.add_subplot(311)
        self.ax_gas_volume = self.canvas.figure.add_subplot(312)
        self.ax_discharge_volume = self.canvas.figure.add_subplot(313)
        # 添加获取令牌按钮
        self.get_token_button = QPushButton('获取令牌')

        self.get_token_button.clicked.connect(lambda: self.start_get_token())

        # 布局设置
        grid = QGridLayout()
        grid.addWidget(self.port_label, 0, 0)
        grid.addWidget(self.port_box, 0, 1)
        grid.addWidget(self.baudrate_label, 1, 0)
        grid.addWidget(self.baudrate_box, 1, 1)
        grid.addWidget(self.start_button, 2, 0, 1, 2)
        grid.addWidget(self.stop_button, 3, 0, 1, 2)

        grid.addWidget(QLabel('状态位信息'), 4, 0)
        grid.addWidget(self.rc_task_status_label, 5, 0, 1, 2)
        grid.addWidget(self.cutter_status_label, 6, 0, 1, 2)
        grid.addWidget(self.battery_voltage_status_label, 7, 0, 1, 2)
        grid.addWidget(self.timeout_status_label, 8, 0, 1, 2)
        grid.addWidget(self.ultra_high_status_label, 9, 0, 1, 2)
        grid.addWidget(self.ultra_fence_status_label, 10, 0, 1, 2)
        grid.addWidget(self.active_cutting_status_label, 11, 0, 1, 2)

        # 添加飞行参数标签到布局
        grid.addWidget(QLabel('飞行参数'), 12, 0)
        grid.addWidget(self.horizontal_speed_label, 13, 0, 1, 2)
        grid.addWidget(self.climbing_speed_label, 14, 0, 1, 2)
        grid.addWidget(self.z_acceleration_label, 15, 0, 1, 2)
        grid.addWidget(self.longitude_label, 16, 0, 1, 2)
        grid.addWidget(self.latitude_label, 17, 0, 1, 2)
        grid.addWidget(self.fusion_altitude_label, 18, 0, 1, 2)
        grid.addWidget(self.pressure_altitude_label, 19, 0, 1, 2)
        grid.addWidget(self.gps_altitude_label, 20, 0, 1, 2)
        grid.addWidget(self.target_altitude_label, 21, 0, 1, 2)
        grid.addWidget(self.pt100_temperature_label, 22, 0, 1, 2)
        grid.addWidget(self.board_temperature_label, 23, 0, 1, 2)
        grid.addWidget(self.battery_temperature_label, 24, 0, 1, 2)
        grid.addWidget(self.battery_voltage_label, 25, 0, 1, 2)
        grid.addWidget(self.capacitor_voltage_label, 26, 0, 1, 2)
        grid.addWidget(self.venting_time_label, 27, 0, 1, 2)
        grid.addWidget(self.ballast_quantity_label, 28, 0, 1, 2)
        grid.addWidget(self.message_label, 29, 0, 1, 2)
        grid.addWidget(self.get_token_button, 30, 0, 1, 2)  # 添加按钮到布局

        grid.addWidget(self.token_url_label, 32, 0)
        grid.addWidget(self.token_url_edit, 32, 1)
        grid.addWidget(self.real_time_url_label, 33, 0)
        grid.addWidget(self.real_time_url_edit, 33, 1)
        # 添加按钮到布局

        data_layout = QVBoxLayout()
        data_layout.addWidget(QLabel('地图视图'))
        data_layout.addWidget(self.map_view)

        data_layout.addWidget(QLabel('接收到的数据:'))
        self.data_text_edit = QTextEdit()
        data_layout.addWidget(self.data_text_edit)

        # 发送数据布局
        self.send_layout = QVBoxLayout()
        self.send_layout.addWidget(self.ballast_send_label)
        self.send_layout.addWidget(self.ballast_send_edit)
        self.send_layout.addWidget(self.time_label)
        self.send_layout.addWidget(self.send_button)
        self.send_layout.addWidget(QLabel('数据曲线'))
        self.send_layout.addWidget(self.canvas)

        main_layout = QHBoxLayout()
        main_layout.addLayout(grid)
        main_layout.addLayout(data_layout)
        main_layout.addLayout(self.send_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
        # 初始化地图
        self.init_map()
        self.closeEvent = self.customCloseEvent

    def scan_ports(self):
        ports = serial.tools.list_ports.comports()
        self.port_box.clear()
        self.port_box.addItems([port.device for port in ports])

    def start_reading(self):
        if self.is_reading:  # 如果已经在读取，则返回
            return
        port = self.port_box.currentText()
        baudrate = int(self.baudrate_box.currentText())
        self.token_url = self.token_url_edit.toPlainText().strip()
        self.real_time_url = self.real_time_url_edit.toPlainText().strip()
        try:
            self.serial = serial.Serial(port, baudrate, timeout=1)
        except serial.SerialException as e:
            print(f"无法打开串口: {e}")
            self.is_reading = False  # 反映串口打开失败的状态
            # 这里可以添加代码来通知用户串口打开失败
            return  # 退出方法，因为串口打开失败

        self.is_reading = True
        try:
            threading.Thread(target=self.read_serial_data, daemon=True).start()  # 启动线程
        except Exception as e:  # 捕获线程启动可能的异常
            print(f"线程启动失败: {e}")
            self.is_reading = False  # 反映线程启动失败的状态
            # 这里可以添加代码来通知用户线程启动失败

    def stop_reading(self):
        self.is_reading = False
        self.save_to_excel()
        if self.serial:
            self.serial.close()


    def send_serial_data(self):
        if self.serial and self.serial.isOpen():
            ballast_value = self.ballast_send_edit.toPlainText()

            data_to_send = f"{ballast_value}\r\n"  # 需要回车换行
            self.serial.write(data_to_send.encode())
            print(f"发送数据: {data_to_send}")

    def read_serial_data(self):
        file_path = "serial_data_log.txt"
        while self.is_reading:
            if self.serial.in_waiting:
                line = self.serial.readline().decode('utf-8', errors='replace').strip()
                print(f"Received line: {line}")
                with open(file_path, "a", encoding='utf-8') as file:
                    file.write(line + '\n')

                self.data_count += 1  # 增加数据计数
                if self.data_count >= self.save_threshold:
                    self.save_to_excel()  # 达到阈值，保存数据
                    self.data_count = 0  # 重置计数器
                current_time = datetime.now()  # 获取当前时间
                formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")  # 格式化时间

                # 创建包含时间和数据的字符串，并添加换行符

                if line.startswith('MXX'):
                    data = line.split(',')
                    if len(data) == 21:
                        lat, lon, alt = float(data[8]), float(data[7]), float(data[10])
                        discharge, gas_volume = float(data[18]), float(data[19])
                        time_str = data[2]
                        hours, minutes, seconds = int(time_str[0:2]), int(time_str[2:4]), int(time_str[4:6])
                        time_in_seconds = hours * 3600 + minutes * 60 + seconds
                        data_with_time = f"{formatted_time}\n {line}\n"
                        self.data_text_edit.append(data_with_time)
                        # 只有当经纬度不为0时，才添加到数组中
                        if lat != 0 and lon != 0:
                            self.latitudes.append(lat)
                            self.longitudes.append(lon)

                        self.altitudes.append(alt)
                        self.discharge_volume.append(discharge)
                        self.gas_volume.append(gas_volume)
                        self.times.append(time_in_seconds)

                        self.update_timer.start(1000)  # 启动定时器，每 100 毫秒更新一次
                        self.data_updated = True
                        self.current_data = data  # 更新当前数据
                        self.dataProcessor.dataUpdated.emit(data)  #
                        print(f"纬度: {lat}, 经度: {lon}")

                else:
                    # 如果不是 MXX 数据行，只显示原始数据
                    self.data_text_edit.append(line)

    def update_all(self, data):
        # 使用传入的 data 参数进行更新
        self.update_system_status(data)
        self.update_map()
        self.plot_data()

    def update_system_status(self, data):
        status = data[3]
        # 更新状态位信息
        self.rc_task_status_label.setText(f'RC任务状态: {data[3]}')
        self.cutter_status_label.setText(f'切断器状态:{status[1]} ')
        self.battery_voltage_status_label.setText(f'电池电压状态:{status[2]} ')
        self.timeout_status_label.setText(f'超时状态: {status[3]} ')
        self.ultra_high_status_label.setText(f'超高状态:{status[4]}  ')
        self.ultra_fence_status_label.setText(f'超围栏状态:{status[5]} ')
        self.active_cutting_status_label.setText(f'主动切断状态:{status[6]} ')

        # 更新飞行参数
        # 更新飞行参数
        self.horizontal_speed_label.setText(f'水平速度: {data[4]} m/s')
        self.climbing_speed_label.setText(f'上升速度: {data[5]} m/s')
        self.z_acceleration_label.setText(f'z加速度: {data[6]} m/s^2')
        self.longitude_label.setText(f'经度: {data[7]}')
        self.latitude_label.setText(f'纬度: {data[8]}')
        self.fusion_altitude_label.setText(f'融合高度: {data[9]} 米')
        self.pressure_altitude_label.setText(f'气压高度: {data[10]} 米')
        self.gps_altitude_label.setText(f'GPS高度: {data[11]} 米')
        self.target_altitude_label.setText(f'目标平飘高度: {data[13]} 米')
        self.pt100_temperature_label.setText(f'PT100温度: {data[14]} 度')
        self.board_temperature_label.setText(f'板上温度: {data[15]} 度')
        self.battery_temperature_label.setText(f'GPS2高度: {data[12]} 米')
        self.battery_voltage_label.setText(f'电池电压: {data[16]}  V')
        self.capacitor_voltage_label.setText(f'电容电压: {data[17]} V')
        self.venting_time_label.setText(f'排气时间: {data[18]} 秒')
        self.ballast_quantity_label.setText(f'抛物量: {data[19]} 个')
        self.message_label.setText((f'北斗上发消息量:{data[20]}'))
        self.time_label.setText((f'时间:{data[2]}'))


    def update_map(self):

        # 更新地图
        if self.latitudes and self.longitudes:
            map_center = [self.latitudes[-1], self.longitudes[-1]]
            m = folium.Map(location=map_center, zoom_start=13)

            # 绘制轨迹线
            folium.PolyLine(
                locations=list(zip(self.latitudes, self.longitudes)),
                color='red',
                weight=5,
                opacity=1
            ).add_to(m)

            # 将地图转换为HTML并显示
            map_html = io.BytesIO()
            m.save(map_html, close_file=False)
            self.map_view.setHtml(map_html.getvalue().decode())
            print("地图已更新")  # 用于调试，确认函数被调用
        else:
            print("没有足够的数据来更新地图")  # 用于调试

    def plot_data(self):
        self.ax_altitude.clear()
        self.ax_gas_volume.clear()
        self.ax_discharge_volume.clear()
        # 只取最近的15个数据点
        if len(self.times) > 15:
            time_labels = [f'{int(t // 3600):02}:{int((t % 3600) // 60):02}:{int(t % 60):02}' for t in self.times[-15:]]
            altitudes = self.altitudes[-15:]
            gas_volumes = self.gas_volume[-15:]
            discharge_volumes = self.discharge_volume[-15:]
        else:
            time_labels = [f'{int(t // 3600):02}:{int((t % 3600) // 60):02}:{int(t % 60):02}' for t in self.times]
            altitudes = self.altitudes
            gas_volumes = self.gas_volume
            discharge_volumes = self.discharge_volume

        self.ax_altitude.plot(time_labels, altitudes, label='Altitude')
        self.ax_altitude.set_xlabel('Time (HH:MM:SS)', fontsize=8)
        self.ax_altitude.set_ylabel('Altitude (m)', fontsize=10)
        self.ax_altitude.tick_params(axis='both', labelsize=5)  # 设置刻度字体大小
        self.ax_altitude.legend(fontsize=6)

        self.ax_gas_volume.plot(time_labels, gas_volumes, label='Discharge Volume', color='green')
        self.ax_gas_volume.set_xlabel('Time (HH:MM:SS)', fontsize=8)
        self.ax_gas_volume.set_ylabel('Discharge(%)', fontsize=10)
        self.ax_gas_volume.tick_params(axis='both', labelsize=5)
        self.ax_gas_volume.legend(fontsize=6)

        self.ax_discharge_volume.plot(time_labels, discharge_volumes, label='Gas Volume', color='red')
        self.ax_discharge_volume.set_xlabel('Time (HH:MM:SS)', fontsize=8)
        self.ax_discharge_volume.set_ylabel('Gas(%)', fontsize=10)
        self.ax_discharge_volume.tick_params(axis='both', labelsize=5)
        self.ax_discharge_volume.legend(fontsize=6)

        plt.tight_layout()  # 自动调整子图参数，使之填充整个图像区域
        self.canvas.draw()

    def init_map(self):
        # 初始化地图（世界地图）
        self.map = Map(location=[0, 0], zoom_start=2)
        data = io.BytesIO()
        self.map.save(data, close_file=False)
        self.map_view.setHtml(data.getvalue().decode())

    def start_get_token(self):
        if self.token_timer.isActive():
            self.token_timer.stop()  # 停止定时器
            print("令牌获取定时器已停止")
        else:
            self.token_timer.start(1000)  # 启动定时器，每 1000 毫秒（1秒）触发一次
            print("令牌获取定时器已启动")

    def get_token(self):
        if self.token:  # 如果已经有令牌，不再获取
            self.token_timer.stop()  # 停止定时器
            return
        try:
            if self.token_url:
                url = self.token_url
                headers = {"Content-Type": "application/json"}
                data = {"username": "admin", "password": "admin123"}
                response = requests.post(url, headers=headers, json=data, timeout=10)
                response.raise_for_status()
                response_data = response.json()
                if response_data.get("code") == 200:
                    self.token = response_data.get("token")
                    print("令牌获取成功:", self.token)

                    self.token_timer.stop()  # 停止获取令牌的定时器
                    self.data_send_timer = QTimer()  # 创建一个新的定时器用于发送数据
                    self.data_send_timer.timeout.connect(
                        self.send_real_time_data)  # 连接定时器的 timeout 信号到 send_real_time_data 方法
                    self.data_send_timer.start(1000)  # 启动定时器，每1000毫秒发送一次数据

                else:
                    print("令牌获取失败:", response_data.get("msg"))
        except ConnectionError as e:
            print(f"连接错误: {e} - 请检查您的网络连接或服务器状态。")
            self.token_timer.stop()

        except Timeout as e:
            print(f"请求超时: {e} - 服务器响应时间过长，请检查您的网络连接或服务器状态。")
            self.token_timer.stop()
        except HTTPError as e:
            print(f"HTTP错误: {e}")
            self.token_timer.stop()
        except RequestException as e:
            print(f"请求异常: {e} - 请检查您的网络连接或服务器状态。")
            self.token_timer.stop()

    def send_real_time_data(self):
        if not self.token:
            print("令牌未获取或已失效")

            return
        if self.token and self.data_updated:
            try:
                url = self.real_time_url
                headers = {"Authorization": self.token}

                data = {
                    "taskId": "test",
                    "status": "1",
                    "longitude": self.current_data[7],
                    "groundSpeed": self.current_data[4],
                    "climbSpeed": self.current_data[5],
                    "acceleratedSpeed": self.current_data[6],
                    "latitude": self.current_data[8],
                    "fusionAltitude": self.current_data[9],
                    "pressureAltitude": self.current_data[10],
                    "gpsAltitude": self.current_data[11],
                    "targetAltitude": self.current_data[13],
                    "pt100Temperature": self.current_data[14],
                    "pcbTemperature": self.current_data[15],
                    # "batteryTemperature": self.current_data[]
                    "batteryVoltage": self.current_data[16],
                    "capacitorVoltage": self.current_data[17],
                    "ventingTime": self.current_data[18],
                    "ballastDropping": self.current_data[19],

                    "time": self.current_data[2],
                }
                print("aaaaaaaaaaaaaa", type(self.current_data[3]))

                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()  # 如果响应状态码不是200，将引发HTTPError
                print("后端数据请求成功")
                self.data_updated = False
            except RequestException as e:
                print("后p端数据请求失败:", e)
                print("后端数据请求失败:", e)
                self.token = ""  # 重置令牌
                self.start_get_token()  # 重新启动定时器获取令牌
        if not self.token:
            print("令牌未获取或已失效")

    def save_to_excel(self):
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Serial Data')

        # 写入表头
        headers = ['Time', 'Latitude', 'Longitude', 'Altitude', 'Ground Speed', 'Climb Speed', 'Accelerated Speed',
                   'Fusion Altitude', 'Pressure Altitude', 'GPS Altitude', 'Target Altitude', 'PT100 Temperature',
                   'PCB Temperature', 'Battery Voltage', 'Capacitor Voltage', 'Venting Time', 'Ballast Dropping',
                   'message']
        for col, header in enumerate(headers):
            sheet.write(0, col, header)

        # 写入数据
        for row in range(len(self.times)):
            sheet.write(row + 1, 0, self.current_data[2])  # 时间
            sheet.write(row + 1, 1, self.current_data[8])  # 纬度
            sheet.write(row + 1, 2, self.current_data[7])  # 经度
            sheet.write(row + 1, 3, self.altitudes[row])  # 高度
            sheet.write(row + 1, 4, self.current_data[4])  # 地面速度
            sheet.write(row + 1, 5, self.current_data[5])  # 上升速度
            sheet.write(row + 1, 6, self.current_data[6])  # 加速度
            sheet.write(row + 1, 7, self.current_data[9])  # 融合高度
            sheet.write(row + 1, 8, self.current_data[10])  # 气压高度
            sheet.write(row + 1, 9, self.current_data[11])  # GPS高度
            sheet.write(row + 1, 10, self.current_data[13])  # 目标高度
            sheet.write(row + 1, 11, self.current_data[14])  # PT100温度
            sheet.write(row + 1, 12, self.current_data[15])  # PCB温度
            sheet.write(row + 1, 13, self.current_data[16])  # 电池电压
            sheet.write(row + 1, 14, self.current_data[17])  # 电容电压
            sheet.write(row + 1, 15, self.current_data[18])  # 排气时间
            sheet.write(row + 1, 16, self.current_data[19])  # 抛物量
            sheet.write(row + 1, 17, self.current_data[20])

        # 生成包含时间戳的文件名
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f'serial_data_{timestamp}.xls'
        workbook.save(filename)
        print(f"数据已保存为 Excel 文件: {filename}")

    def customCloseEvent(self, event):
        # 在关闭窗口前保存数据
        self.save_to_excel()
        # 调用父类的closeEvent处理其他关闭逻辑
        self.token_timer.stop()
        self.data_send_timer.stop()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    reader = SerialReader()
    reader.show()
    sys.exit(app.exec_())