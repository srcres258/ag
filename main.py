"""
模仿南京大学蒋炎岩老师在操作系统课上使用的 ag 工具, 自己开发的一款简易的适用于终端 CLI 的大模型调用 ag 工具.
基于 OpenRouter 的 API, 支持多种类 LLM.

Credits to: https://jyywiki.cn/OS/2024/ (有时间的话去听一下这课, 相信我, 受益匪浅!)

虽然可以调用多种 LLM, 但是还是提醒一下, 注意自己的 token 用量, 省着点儿用吧...
稍微先进一点的 LLM, 耗 token 如流水, 霍霍几下自己充的 token 就没了, 当心哦! (`・ω・´)

Author: srcres258
"""

import argparse
import sys
import os
import re
import json
from typing import List, Dict
from datetime import datetime

from openai import OpenAI
from termcolor import colored
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import ANSI

bindings = KeyBindings()


@bindings.add('c-d')
def _(event):
    """Pressing Ctrl-D will exit the user input prompt."""

    buffer = event.app.current_buffer
    event.app.exit(result=buffer.text)


parser = argparse.ArgumentParser(
    description='ag - a simple CLI tool for calling '
    'large language models via OpenRouter API')

DEFAULT_MODEL_CHOICES: List[str] = [
    'deepseek-v3.1', 'deepseek-r1t2', 'bytedance-seed-1.6', 'hunyuan-a13b',
    'gpt-oss-120b', 'gpt-4o-mini', 'grok-4.1-fast'
]
MODEL_CHOICE_TO_ID: Dict[str, str] = {
    'deepseek-v3.1': 'nex-agi/deepseek-v3.1-nex-n1:free',
    'deepseek-r1t2': 'tngtech/deepseek-r1t2-chimera:free',
    'bytedance-seed-1.6': 'bytedance-seed/seed-1.6-flash',
    'hunyuan-a13b': 'tencent/hunyuan-a13b-instruct',
    'gpt-oss-120b': 'openai/gpt-oss-120b',
    'gpt-4o-mini': 'openai/gpt-4o-mini',
    'grok-4.1-fast': 'x-ai/grok-4.1-fast'
}

parser.add_argument(
    '-q',
    '--quiet',
    action='store_true',
    help='Quiet mode, disable outputs in prompting intentions.')
parser.add_argument(
    '-l',
    '--multi-line',
    action='store_true',
    help=('Multi-line mode, input and output can span multiple lines. '
          'If not set, single-line mode is used.'))
parser.add_argument(
    '-i',
    '--interpret',
    action='store_true',
    help=
    ('Interpret content directly from the standard input and output the result from the LLM. '
     'If set, quiet mode will be automatically enabled and no more rounds of communication with LLM will be accepted.'
     ))
parser.add_argument(
    '-c',
    '--save-comm',
    action='store_true',
    help=
    ('Save the communication history to a timestamped JSON file. '
     'The output file will be put under the data directory specified by --datadir option.'
     ))
parser.add_argument(
    '-r',
    '--save-reply-markdown',
    action='store_true',
    help=
    ('Save the LLM reply to a timestamped Markdown file. '
     'The output file will be put under the data directory specified by --datadir option.'
     ))

parser.add_argument(
    '-m',
    '--model',
    type=str,
    choices=DEFAULT_MODEL_CHOICES,
    default=DEFAULT_MODEL_CHOICES[0],
    help='Specify the LLM model to use (default: deepseek-v3.1).')
parser.add_argument(
    '-s',
    '--starter-comm-file',
    type=str,
    default='',
    help=
    ('Path to a JSON file containing starter communication history. '
     'If set, the communication history from the file will be prepended to each request.'
     ))

parser.add_argument(
    '--custom-model',
    type=str,
    default='',
    help=
    ('Specify a custom LLM model which will be used to send API requests to OpenRouter. '
     'If set, the --model option will be ignored.'))
parser.add_argument(
    '--api-key-file',
    type=str,
    default='~/.ag/openrouter_api_key',
    help=
    'Path to the file containing the OpenRouter API key (default: ~/.ag/openrouter_api_key).'
)
parser.add_argument(
    '--datadir',
    type=str,
    default='~/.ag/data',
    help=
    'Directory to save communication history and replies (default: ~/.ag/data).'
)


def gen_message(raw_input: str) -> Dict[str, object]:
    """转换请求输入为 OpenRouter API 消息格式, 随后可以用其调用 OpenRouter API 上的 LLM."""

    reg = r'\{\{file:([^\}]+)\}\}'

    def replace_file(m: re.Match) -> str:
        path = re.findall(reg, m.group(0))[0]
        with open(path, 'r') as f:
            return f.read()

    raw_input = re.sub(reg, replace_file, raw_input)
    message = {
        'role': 'user',
        'content': [{
            'type': 'text',
            'text': raw_input
        }]
    }

    return message


def gen_timestamp_str() -> str:
    """获取当前时间并生成格式化后的时间戳字符串."""

    current_time = datetime.now()
    formatted_time = current_time.strftime("%Y-%m-%d-%H-%M-%S")

    return formatted_time


def save_to_new_markdown(datadir: str, content: str) -> str:
    """将内容保存到 datadir 目录下以时间戳命名的 Markdown 文件中. 返回文件名."""

    timestamp_str = gen_timestamp_str()
    filename = f"reply-{timestamp_str}.md"
    filepath = os.path.join(datadir, filename)
    with open(filepath, 'w') as f:
        f.write(content)

    return filename


def save_message_history(datadir: str,
                         message_history: List[Dict[str, object]]) -> str:
    """将消息历史保存到 datadir 目录下以时间戳命名的 JSON 文件中. 返回文件名."""

    timestamp_str = gen_timestamp_str()
    filename = f"comm-history-{timestamp_str}.json"
    filepath = os.path.join(datadir, filename)
    with open(filepath, 'w') as f:
        json.dump(message_history, f, indent=2)

    return filename


def main() -> int:
    """程序主逻辑."""

    # --- 解析命令行参数 ---
    args = parser.parse_args()

    # --- 接收并处理命令行参数 ---
    quiet = args.quiet
    multi_line = args.multi_line
    interpret = args.interpret
    if interpret:
        quiet = True
    save_comm = args.save_comm
    save_reply_markdown = args.save_reply_markdown

    model = args.model
    starter_comm_file = os.path.expanduser(args.starter_comm_file)

    custom_model = args.custom_model
    if custom_model and custom_model != '' and len(custom_model) > 0:
        model_id = custom_model
    else:
        model_id = MODEL_CHOICE_TO_ID[model]
    api_key_file_path = os.path.expanduser(args.api_key_file)
    datadir = os.path.expanduser(args.datadir)

    if quiet:

        def do_nothing_print(*args, **kwargs) -> None:
            pass

        print_opt = do_nothing_print
    else:
        print_opt = print

    if not os.path.exists(datadir):
        print_opt(
            f"Note: Data directory {datadir} does not exist. Creating it...")
        os.makedirs(datadir)

    # --- 加载与 LLM 的历史对话 ---
    message_history = []
    if starter_comm_file and starter_comm_file != '' and len(
            starter_comm_file) > 0:
        try:
            with open(starter_comm_file, 'r') as f:
                starter_messages = json.load(f)
                message_history.extend(starter_messages)
            print_opt(
                f"Loaded starter communication history from {starter_comm_file}."
            )
        except FileNotFoundError:
            print_opt(
                f"Error: Starter communication file not found at {starter_comm_file}. Please check the path."
            )
            return 1
        except json.JSONDecodeError:
            print_opt(
                f"Error: Failed to parse JSON from {starter_comm_file}. Please check the file content."
            )
            return 1

    # --- 读取 OpenRouter API Key ---
    try:
        with open(api_key_file_path, 'r') as f:
            api_key = f.read().strip()
    except FileNotFoundError:
        print_opt(
            f"Error: API key file not found at {api_key_file_path}. Please create the file and add your OpenRouter API key."
        )
        return 1
    if not api_key or api_key == '' or len(api_key) == 0:
        print_opt("Error: API key is empty. Please check your API key file.")
        return 1

    # --- 初始化 OpenAI 客户端 ---
    client = OpenAI(api_key=api_key, base_url='https://openrouter.ai/api/v1')

    exitcode = 0

    # --- 循环读取用户输入并通过 LLM 进行响应 ---
    try:
        get_message_round = lambda: len(message_history) // 2

        if multi_line:
            print_opt("Input mode: multi-line")
            print_opt(
                "Tip: Press Ctrl+D to end your input; Ctrl+C to exit the program."
            )
        else:
            print_opt("Input mode: single-line")
            print_opt(
                "Tip: Press Enter to end your input; Ctrl+C to exit the program."
            )
        while True:
            prompt_str = colored(f"👤 Human ({get_message_round()})> ", 'green')
            if interpret:
                user_input = sys.stdin.read()
            elif multi_line:
                session = PromptSession(
                    message='' if quiet else ANSI(prompt_str),
                    key_bindings=bindings,
                    multiline=True)
                user_input = session.prompt()
            else:
                print_opt(prompt_str, end='', flush=True)
                user_input = input()
            if user_input.strip() == "" or len(user_input.strip()) == 0:
                continue
            message = gen_message(user_input)
            message_history.append(message)

            response = client.chat.completions.create(model=model_id,
                                                      messages=message_history,
                                                      stream=True)
            print_opt(colored(f"🤖 Robot ({get_message_round()})> ", 'red'),
                      end='',
                      flush=True)
            full_reply = ""
            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_reply += content
                    sys.stdout.write(content)
                    sys.stdout.flush()
            print_opt()  # 换行

            if save_reply_markdown:
                filename = save_to_new_markdown(datadir, full_reply)
                print_opt(
                    colored(
                        f"LLM reply saved to Markdown file: {os.path.join(datadir, filename)}.",
                        'dark_grey'))
            message_history.append({
                'role':
                'assistant',
                'content': [{
                    'type': 'text',
                    'text': full_reply
                }]
            })

            if interpret:
                break
    except KeyboardInterrupt:
        print_opt()
        print_opt("Keyboard interrupt received!")
    except Exception as e:
        print_opt()
        print_opt(f"An unexpected error occurred: {e}")
        exitcode = 1

    # --- 保存与 LLM 的对话记录 ---
    if save_comm:
        filename = save_message_history(datadir, message_history)
        print_opt(
            f"Communication history saved to {os.path.join(datadir, filename)}."
        )

    print_opt()
    print_opt("Exiting..." if exitcode == 0 else "Exiting with errors...")
    return exitcode


if __name__ == '__main__':
    sys.exit(main())
