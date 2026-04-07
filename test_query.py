#!/usr/bin/env python3
import requests
import json
import time

url = "http://localhost:8080/mcp/generate_sql"
headers = {"Content-Type": "application/json"}
data = {"query": "查询所有用户"}

print(f"发送请求: {url}")
print(f"请求体: {json.dumps(data, ensure_ascii=False)}")
print(f"开始时间: {time.strftime('%H:%M:%S')}")

try:
    response = requests.post(url, headers=headers, json=data, timeout=120)
    print(f"结束时间: {time.strftime('%H:%M:%S')}")
    print(f"\n状态码: {response.status_code}")
    print(f"响应头: {response.headers}")
    print(f"\n响应内容:")
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))
except Exception as e:
    print(f"结束时间: {time.strftime('%H:%M:%S')}")
    print(f"错误: {e}")
    if 'response' in locals():
        print(f"响应内容: {response.text}")
