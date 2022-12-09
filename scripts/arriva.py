#!/usr/bin/env python3
"""
! You won't get much use out of this script unless you live in the UK, Yorksire area, and have the bus operator
'Arriva' running through your area. This script is designed to automate the process of connecting to the Arriva
free public Wi-Fi, and managing automatically authenticating ("agreeing" to the T&Cs) with the captive portal,
and then automatically connecting my VPN (which you almost definitely don't have).

If you *do* have Arriva in your area, you can use this script even without the VPN. Just answer 'no' to any VPN
related questions.
Alternatively, you can edit the script to rename the wireguard connection names, or you can run the following
command:

# ln /etc/wireguard/Laptop.conf /etc/wireguard/<your-config-file>

This will link /etc/wireguard/Laptop.conf to your own config file, and the script will use that instead.
"""

import subprocess
import requests
import click
from bs4 import BeautifulSoup
from urllib.parse import urlsplit, parse_qs
import textwrap
import time
from rich import get_console
from rich.prompt import Confirm
from functools import partial

console = get_console()
# params = {
#     "res": "notyet",  # authentication status
#     "uamip": "10.0.0.1",  # router?
#     "uamport": "3990",  # router port or something (web interface?)
#     "challenge": "angiabgouawguawg",  # Challenge (looks interesting!)
#     "called": "AA-BB-CC-DD-EE-FF",  # Unknown MAC address - MAC of router?,
#     "mac": "AA-BB-CC-DD-EE-FF",  # Our MAC address
#     "ip": "10.0.0.11",  # Some random internal IP - probably not important.
#     "nasid": "12345",  # I think this is an internal thing
#     "sessionid": "auwbgiuagw99nnajkakjwgb",  # Session ID - pair with challenge? Looks important nonetheless
#     "userurl": "detectportal.firefox.com",  # The service used to detect the portal - useless
#     "md": "8912937AIWGIBAGW",  # Some random hexadecimal.
# }


def confirm(question: str, yes: bool = False):
    return yes or Confirm.ask(question, console=console)


def qs_to_dict(url: str, flatten: bool = False) -> dict:
    params: dict = parse_qs(urlsplit(url).query)
    if flatten:
        return {k: v[0] for k, v in params.items()}
    return params


def do_request(
    session, url: str, stage: str, *args, method: str = "GET", **kwargs
) -> requests.Response | None:
    with console.status("GET " + textwrap.shorten(url, 100)):
        try:
            start = time.time()
            response = session.request(method, url, *args, **kwargs)
            end = time.time()
        except requests.ConnectionError:
            console.log(f"[red]:warning: Failed to connect to {stage} - are you connected to wifi?")
            return
        except KeyboardInterrupt:
            console.log(f"[red]:warning: Connection to {stage} aborted!")
            return
    console.log(f"[green]:white_check_mark: GET {response.url}: {response.status_code} ({round((end - start)*1000)}ms)")
    return response


def cycle_net_connection(off_first: bool = True, on_after: bool = True, sleep_time: int = 2):
    with console.status("Cycling wifi connection") as status:
        commands = []
        if off_first is True:
            commands.append(("nmcli", "connection", "down", "arriva-wifi"))
        if on_after is True:
            commands.append(("nmcli", "connection", "up", "arriva-wifi"))
        if sleep_time > 0:
            commands.append(("sleep", str(sleep_time)))

        for cmd in commands:
            status.update(status="Running " + repr(" ".join(cmd)))
            x = subprocess.run(cmd, capture_output=True)
            if x.returncode != 0:
                console.log("[red]$ " + " ".join(cmd))
            else:
                console.log("[green]$ " + " ".join(cmd))


def get_canonical_response(yes: bool, n: int = 0):
    assert n <= 5, "Too many retries."
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64; rv:107.0) Gecko/20100101 Firefox/107.0"
    get = partial(do_request, session)
    canonical_response = get("http://detectportal.firefox.com/canonical.html", "portal detecter", allow_redirects=False)
    if canonical_response is None:
        raise RuntimeError

    if canonical_response.status_code != 302:
        if canonical_response.status_code == 200:
            console.log("[green]:white_check_mark: Already connected to WiFi!")
            if not confirm("Do you want to cycle connection?", yes):
                raise RuntimeError
            else:
                cycle_net_connection(sleep_time=3)
                return get_canonical_response(yes, n + 1)

        console.log(
            ":[red]warning: Failed to detect portal - got HTTP %s for firefox detection portal!"
            % canonical_response.status_code
        )
        raise RuntimeError
    return canonical_response, session, get


def check_arriva_wifi_connection(yes: bool = False):
    with console.status("Verifying WiFi connection"):
        active = bool(
            subprocess.run(
                ("nmcli", "connection", "show", "--active", "arriva-wifi"), capture_output=True, encoding="utf-8"
            ).stdout
        )
        wifi_list = subprocess.run(("nmcli", "device", "wifi", "list"), capture_output=True, encoding="utf-8")
        _conn = subprocess.run(("nmcli", "connection", "show", "--active"), capture_output=True, encoding="utf-8")
    if not active:
        if _conn.stdout == "\n":
            console.log("[red]:warning: Not connected to WiFi!")
            if wifi_list.returncode == 0 and "arriva-wifi" in wifi_list.stdout:
                if confirm("Do you want to try connecting to arriva wifi?", yes):
                    cycle_net_connection()
                    return check_arriva_wifi_connection(yes)
            else:
                return False
        else:
            console.log("[yellow]:warning: You are not connected to a different network to the arriva network.")
            if wifi_list.returncode == 0 and "arriva-wifi" in wifi_list.stdout:
                if confirm("Do you want to try connecting to arriva wifi?", yes):
                    cycle_net_connection()
                    return check_arriva_wifi_connection(yes)
            return False

    return True


def kill_vpns():
    with console.status("Bringing down VPN (if its up)"):
        _vpns = ("Laptop", "Laptop-Pi", "Laptop-Internal", "Laptop-SS")
        for vpn in _vpns:
            subprocess.run(("wg-quick", "down", vpn), capture_output=True)


@click.command()
@click.option("--yes", "-Y", is_flag=True, help="Skip confirmation prompts (assume YES)")
def main(yes: bool):
    kill_vpns()
    okay = check_arriva_wifi_connection(yes)
    if not okay:
        return
    try:
        canonical_response, _, get = get_canonical_response(yes)
    except RuntimeError:
        return
    target_url = canonical_response.headers["Location"]
    console.log("[dim i]Following redirect from detection portal (to: {})".format(target_url))
    portal_response = get(target_url, "portal")
    if portal_response is None:
        return

    if portal_response.status_code != 200:
        console.log("[red]Failed to connect to portal: HTTP %s" % portal_response.status_code)
        return

    params = qs_to_dict(portal_response.url)

    url = "https://portal.moovmanage.com/aukb-yorkshire/connect.php"
    params2 = params.copy()
    params2["status"] = ("connection-request",)
    params2["submit.x"] = "50"
    params2["submit.y"] = "20"  # I'm not entirely sure what these do?
    url = url.format("&".join([f"{x}={y}" for x, y in params2.items()]))

    response = get(url, "connecter", params=params2)
    if not response:
        return
    soup = BeautifulSoup(response.text, "html.parser")
    tags = soup.find_all("meta")
    with console.status("Locating refresh tag amongst {!s} meta tags...".format(len(tags))):
        for tag in tags:
            try:
                if tag["http-equiv"] == "refresh":
                    content = tag["content"]
                    break
            except KeyError:
                continue
        else:
            console.log("[red]Failed to find callback URL.")
            return

    url = content[6:]
    response = get(url, "callback", allow_redirects=False)
    if not response:
        return
    if response.status_code == 302:
        url = response.headers["Location"]
        params = qs_to_dict(url, True)
        if params["res"] == "success":
            console.log("[green]:white_check_mark: You should now have access to arriva's free wifi.")
        else:
            console.log("[yellow]Went through the auth flow and got '{}' for res.")
            return
    else:
        console.log("[red] " + response.text)
        console.log("[red]Failed to complete auth flow.")
        return

    console.log("[dim]Checking internet connectivity...")
    response = get("https://httpbin.org/anything", "httpbin")
    if not response:
        return
    if response.status_code == 200:
        console.log("[green]:white_check_mark: You should now have access to the internet.")
        console.log("HTTPBin data:")
        console.print_json(data=response.json(), indent=4)
        if Confirm.ask("Would you like to start the 'Laptop' VPN?", console=console):
            with console.status("Starting VPN"):
                x = subprocess.run(("wg-quick", "up", "Laptop"), capture_output=True)
            if x.returncode != 0:
                console.log("[red]Failed to start VPN.")
                console.log("[red]Attempting to reverse VPN connection")
                with console.status("Reversing VPN connection"):
                    x = subprocess.run(("wg-quick", "down", "Laptop"), capture_output=True)
                if x.returncode != 0:
                    console.log("[red]Failed to reverse VPN connection.")
                    console.log("[red]Please check your VPN configuration.")
                else:
                    console.log("[yellow]:warning: VPN connection reversed.")
            else:
                console.log("[green]:white_check_mark: VPN connection started.")
                console.log("[dim]Checking VPN connectivity...")
                response = do_request(requests, "https://httpbin.org/anything", "httpbin")
                if not response or response.status_code != 200:
                    console.log("[red]Failed to connect to internet - are you connected to wifi?")
                    console.log("[red]Attempting to reverse VPN connection")
                    with console.status("Reversing VPN connection"):
                        x = subprocess.run(("wg-quick", "down", "Laptop"), capture_output=True)
                    if x.returncode != 0:
                        console.log("[red]Failed to reverse VPN connection.")
                        console.log("[red]Please check your VPN configuration.")
                    else:
                        console.log("[yellow]:warning: VPN connection reversed.")
                    return
                else:
                    console.log("[green]:white_check_mark: You should now have access to the internet over VPN.")
                    console.log("HTTPBin data:")
                    console.print_json(data=response.json(), indent=4)

                    if Confirm.ask("Do you want to do a latency check?", console=console):
                        times = []
                        for i in range(10):
                            start = time.time()
                            response = do_request(requests, "https://httpbin.org/anything", "httpbin")
                            if not response or response.status_code != 200:
                                end = time.time_ns()
                            else:
                                end = time.time()
                            times.append(end - start)
                        console.log("[dim]Average Latency: {:.2f}ms".format(sum(times) / len(times) * 1000))
                        console.log("[dim]Max Latency: {:.2f}ms".format(max(times) * 1000))
                        console.log("[dim]Min Latency: {:.2f}ms".format(min(times) * 1000))
    else:
        console.log("[red]Failed to connect to internet - are you connected to wifi?")
        return


if __name__ == "__main__":
    main()
