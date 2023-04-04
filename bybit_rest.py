from urllib.parse import quote_plus
import urllib3
import requests
import json
import hmac
import hashlib
import time


def get_position_list(api_key, api_secret, is_prod, symbol):
    kwargs = {
        "api_key": api_key,
        "symbol": symbol,
        "timestamp": round(time.time() * 1000),
    }

    param_str = link_params(kwargs)
    sign_real = generate_signiture(param_str, api_secret)

    method = "GET"
    url = get_api_url(is_prod) + "bybit.com/v2/private/position/list"

    return send_req(url, method, kwargs, param_str, sign_real)


def get_api_url(is_prod):
    if is_prod:
        return "https://api."
    else:
        return "https://api-testnet."


def link_params(params: dict()):
    param_str = ""
    for key in sorted(params.keys()):
        v = params[key]
        if isinstance(params[key], bool):
            if params[key]:
                v = "true"
            else:
                v = "false"
        param_str += f"{key}={v}&"
    param_str = param_str[:-1]
    return param_str


def generate_signiture(param_str, api_secret):
    hash = hmac.new(bytes(api_secret, "utf-8"), param_str.encode("utf-8"),
                    hashlib.sha256)
    signature = hash.hexdigest()
    sign_real = {
        "sign": signature
    }
    return sign_real


def send_req(url, method, params, param_str, sign_real):
    param_str = quote_plus(param_str, safe="=&")
    full_param_str = f"{param_str}&sign={sign_real['sign']}"

    if method == "GET":
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        body = None
    else:
        headers = {"Content-Type": "application/json"}
        body = dict(params, **sign_real)

    urllib3.disable_warnings()
    s = requests.session()
    s.keep_alive = False

    # Send a request to the futures API
    if method == "POST":
        response = requests.request(method, url, data=json.dumps(body),
                                    headers=headers, verify=False)
    else:  # GET
        response = requests.request(method, f"{url}?{full_param_str}",
                                    headers=headers, verify=False)
    return json.loads(response.text)
