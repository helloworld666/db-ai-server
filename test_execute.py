#!/usr/bin/env python3
import requests
import json

url = "http://localhost:8080/mcp/execute_sql"
headers = {"Content-Type": "application/json"}
sql = "SELECT * FROM sys_user"

print(f"发送请求: {url}")
print(f"SQL: {sql}")

try:
    response = requests.post(url, headers=headers, json={"sql": sql}, timeout=30)
    print(f"\n状态码: {response.status_code}")
    print(f"\n响应内容:")
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))
except Exception as e:
    print(f"错误: {e}")
    if 'response' in locals():
        print(f"响应内容: {response.text}")
