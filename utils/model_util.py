
import json
import time
import traceback

import requests
from loguru import logger
import config

def process_deepseek_query(query, prompt, temperature=1, max_tokens=2000):
    # logger.info(f"query:{query}")
    # logger.info(f"prompt:{prompt}")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.deepseek_api_key}",
    }
    body = {
        "temperature": temperature,
        "stream": True,
        # "model": "deepseek-v4-flash",
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": query},
        ],
        "max_tokens": max_tokens,
    }
    request_count = 1
    request_time = time.time()
    while True:
        start_time = time.time()
        try:
            response = requests.post( f"https://api.deepseek.com/chat/completions", headers=headers, json=body, timeout=(30, 120) , stream=True)
            if 400 == response.status_code and 'Content Exists Risk' in response.text:
                return "需人工补充"
            response.raise_for_status()
            full_content = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0]["delta"]
                            content = delta.get("content", "")
                            if content:
                                full_content += content
                        except json.JSONDecodeError:
                            pass
            model_output = full_content

            if len(model_output) < 1:
                return process_deepseek_query(query, prompt, temperature, max_tokens)
            # logger.info(f"api.deepseek.com请求耗时：{time.time() - start_time} 方法总耗时：{time.time() - request_time} request_count:{request_count} model_output:{model_output}")
            return model_output
        except Exception as e:
            logger.error(f"api.deepseek.com异常：{e} 请求耗时：{time.time() - start_time} 方法总耗时：{time.time() - request_time} request_count:{request_count}")
            logger.error(f"api.deepseek.com异常：{traceback.format_exc()}")
            request_count += 1
            time.sleep(1)