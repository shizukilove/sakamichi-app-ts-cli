import os
import re
import json
import httpx
import UnityPy

s46_member_data = json.load(open("./.config/member.data.json", "r", encoding="utf-8"))[
    "sakurazaka46"
]
h46_member_data = json.load(open("./.config/member.data.json", "r", encoding="utf-8"))[
    "hinatazaka46"
]


def downloader_mode_5(
    asset_type: str,
    catalog: str,
    path_server: str,
    path_local: str,
    from_index: int = 0,
    to_index: int = 0,
    mode: str = "catalog",
) -> None:
    urlserver = None

    print(f"catalog: {catalog}")

    create_download_log_files(asset_type)

    data_table = (
        [
            {
                "assetBundleName": os.path.join(folderpath, filename),
                "fileSize": str(os.path.getsize(os.path.join(folderpath, filename))),
            }
            for folderpath, _, filepath in os.walk(
                os.path.join(".temp", asset_type.split("_")[0].title()), topdown=True
            )
            for filename in filepath
        ]
        if mode == "local"
        else json.load(open(catalog, "r", encoding="utf-8"))["data"]
        if mode == "catalog"
        else []
    )
    filtered_data = [
        data
        for data in data_table
        if (100000 <= int(data["fileSize"]) <= 1000000 and "card" in asset_type)
        or (int(data["fileSize"]) >= 1000000 and "movie" in asset_type)
    ] or []
    datas = []
    if mode == "catalog":
        urlserver = path_server.split("/")
        urlserver[-2] = catalog.split("_")[2]
        if 0 <= from_index < len(filtered_data) and 0 < to_index <= len(filtered_data):
            datas = filtered_data[from_index:to_index]
        elif from_index >= 0 and to_index >= len(filtered_data):
            datas = filtered_data[from_index:]
        elif from_index == 0 and to_index == 0:
            datas = filtered_data
    elif mode == "local":
        datas = filtered_data
    print(f"Data length      : {str(len(data_table))}")
    print(f"Requested assets : {asset_type}")
    print(f"Length           : {str(len(filtered_data))}")
    print(
        f"Requested length : {str(len(datas))} ({str(from_index)} to {str(to_index)})"
    )
    print(f"Mode             : {mode}")

    def executor(filename: str) -> None:
        if "movie" in asset_type and os.path.exists(
            os.path.join(path_local, f"{filename.split('/')[-1]}.mp4")
        ):
            print(
                f"\x1b[38;5;11m{filename.split('/')[1]}.mp4 already exists\x1b[0m")
            return f"{filename.split('/')[1]}.mp4"
        else:
            data = None
            if mode == "catalog":
                print("/".join(urlserver) + "/" + filename)
                with httpx.stream(
                    "GET", "/".join(urlserver) + "/" + filename, timeout=None
                ) as res:
                    if res.status_code != 200:
                        print("\x1b[38;5;1mWhoops, server error\x1b[0m")
                        exit(1)
                    data = bytearray(res.read())
            else:
                data = bytearray(open(filename, "rb").read())
            key = data[7]
            for i in range(150):
                data[i] ^= key
            assets = UnityPy.load(bytes(data))
            if assets.objects and "card" in asset_type:
                for asset in assets.objects:
                    matcher = (
                        r"(^\d{7}_|^\d{3}$|^\d{3}_)"
                        if asset_type == "sakukoi_card"
                        else r"(^\d{8}_\d|^\d{3}_\d$)"
                    )
                    if asset.type.name == "Texture2D" and re.match(
                        matcher, asset.read().name
                    ):
                        member_data = [
                            data
                            for data in (
                                s46_member_data
                                if "sakukoi" in asset_type
                                else h46_member_data
                            )
                            if not data[asset_type.split("_")[0]] == ""
                            and re.search(
                                f"{data['gen']+data[asset_type.split('_')[0]]}",
                                asset.read().name[0:3]
                                if len(asset.read().name) <= 5
                                else asset.read().name[3:6]
                                if 6 <= len(asset.read().name) <= 10
                                else "000",
                            )
                        ]
                        folder_path = (
                            os.path.join(
                                path_local,
                                f"{member_data[0]['gen']}. {member_data[0]['name']}",
                            )
                            if member_data
                            else os.path.join(path_local, "00. 不特定")
                        )
                        if member_data and (member_data[0]["gen"] == "1" or member_data[0]["gen"] == "2"):
                            print(f"skip {asset.read().name}")
                            return asset.read().name
                        if not os.path.exists(folder_path):
                            os.makedirs(folder_path)

                        filename = os.path.join(
                            folder_path, f"{asset.read().name}.png")
                        file_exists = os.path.exists(filename)
                        count = 1
                        while file_exists:
                            print(
                                f"\x1b[38;5;11m{filename} already exist\x1b[0m"
                            )
                            filename = os.path.join(
                                folder_path, f"{asset.read().name}-{count}.png")
                            print(filename)
                            file_exists = os.path.exists(filename)
                            print(file_exists)
                            count += 1

                        print(filename)
                        asset.read().image.save(
                            os.path.join(folder_path, filename)
                        )
                        print(f"{asset.read().name} saved!")
                        return asset.read().name
            elif not assets.objects and "movie" in asset_type:
                if not os.path.exists(path_local):
                    os.makedirs(path_local)
                key = data[15]
                for i in range(150):
                    data[i] ^= key
                open(
                    os.path.join(
                        path_local, f"{filename.split('/')[-1]}.mp4"), "wb"
                ).write(bytes(data))
                print(f"{filename.split('/')[1]}.mp4 saved!")
                return f"{filename.split('/')[1]}.mp4"
        if mode == "local":
            os.remove(filename)

    download_log_file_name = f".download_log/{asset_type}_download_log.txt"
    file = open(download_log_file_name, "a")
    downloaded_dict = get_downloaded_dict(download_log_file_name)
    for assetBundle in datas:
        assetBundleName = assetBundle["assetBundleName"]
        if is_downloaded(assetBundleName, downloaded_dict):
            continue
        filename = executor(assetBundleName)
        line = f"{assetBundleName}|{filename if filename is not None else ''}\n"
        file.write(line)
    file.close()


def get_downloaded_dict(download_log_file_name: str) -> dict[str, str]:
    with open(download_log_file_name, "r") as file:
        lines = file.read().splitlines()
    dict = {}
    for line in lines:
        arr = line.split("|")
        dict[arr[0]] = line
    return dict


def is_downloaded(name: str, dict: dict[str, str]):
    if name in dict:
        return True
    return False


def create_download_log_files(asset_type: str):
    folder = ".download_log"
    if not os.path.exists(folder):
        os.makedirs(folder)
    filename = f"{folder}/{asset_type}_download_log.txt"
    if not os.path.exists(filename):
        with open(filename, "w") as file:
            pass
