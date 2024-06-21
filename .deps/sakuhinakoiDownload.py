import os
import re
import json
import httpx
import UnityPy
from enum import Enum

s46_member_data = json.load(open("./.config/member.data.json", "r", encoding="utf-8"))[
    "sakurazaka46"
]
h46_member_data = json.load(open("./.config/member.data.json", "r", encoding="utf-8"))[
    "hinatazaka46"
]

download_log_folder = ".download_log"

RESOURCE_TYPE = "RESOURCE_TYPE"
FILENAME = "FILENAME"


class ResourceType(Enum):
    CARD = "card"
    MOVIE = "movie"


def downloader_mode_5(
    asset_type: str,
    catalog: str,
    path_server: str,
    path_local: str,
    from_index: int = 0,
    to_index: int = 0,
    mode: str = "catalog",
) -> None:
    print(f"catalog: {catalog}")

    download_log_file_name = f"{asset_type.split('_')[0]}_download_log.txt"

    create_download_log_files(download_log_file_name)

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
        if (50000 <= int(data["fileSize"]))
    ] or []

    urlserver = path_server.split("/")
    urlserver[-2] = catalog.split("_")[2]

    print(f"Data length      : {str(len(data_table))}")
    print(f"Requested assets : {asset_type}")
    print(f"Length           : {str(len(filtered_data))}")
    print(f"Mode             : {mode}")

    file = open(f"{download_log_folder}/{download_log_file_name}", "a")
    print(file.name)
    downloaded_dict = get_downloaded_dict(download_log_file_name)
    for assetBundle in filtered_data:
        assetBundleName = assetBundle["assetBundleName"]
        if is_downloaded(assetBundleName, downloaded_dict):
            continue
        result = executor(assetBundleName, urlserver,
                          path_local, asset_type.split("_")[0], mode)
        filename = ""
        resource_type = ""
        if result is not None:
            filename = result[FILENAME] if FILENAME in result else ""
            resource_type = result[RESOURCE_TYPE] if RESOURCE_TYPE in result else ""
        line = f"{assetBundleName}|{resource_type}|{filename}\n"
        file.write(line)
    file.close()


def executor(assetBundleName: str, urlserver: list[str], path_local: str, app_type: str, mode: str) -> dict[str, str] | None:
    if os.path.exists(
        os.path.join(
            path_local, f"/movie/{assetBundleName.split('/')[-1]}.mp4")
    ):
        print(
            f"\x1b[38;5;11m{assetBundleName.split('/')[1]}.mp4 already exists\x1b[0m")
        return {FILENAME: f"{assetBundleName.split('/')[1]}",
                RESOURCE_TYPE: ResourceType.MOVIE.value}

    data = get_resource_data(assetBundleName, urlserver, mode)
    key = data[7]
    for i in range(150):
        data[i] ^= key
    assets = UnityPy.load(bytes(data))

    if assets.objects:
        return handle_card(assets, f"{path_local}/card", app_type, assetBundleName)

    return handle_video(data, assetBundleName, f"{path_local}/movie")


def get_resource_data(filename: str, urlserver: list[str], mode: str) -> bytearray:
    if mode == "local":
        return bytearray(open(filename, "rb").read())

    print("/".join(urlserver) + "/" + filename)
    with httpx.stream(
        "GET", "/".join(urlserver) + "/" + filename, timeout=None
    ) as res:
        if res.status_code != 200:
            print("\x1b[38;5;1mWhoops, server error\x1b[0m")
            exit(1)
        return bytearray(res.read())


def handle_video(data, filename, path_local) -> dict[str, str] | None:
    if not os.path.exists(path_local):
        os.makedirs(path_local)
    key = data[15]
    for i in range(150):
        data[i] ^= key
    # magic.from_buffer(data).read(2048)
    open(
        os.path.join(
            path_local, f"{filename.split('/')[-1]}.mp4"), "wb"
    ).write(bytes(data))
    print(f"{filename.split('/')[1]}.mp4 saved!")
    return {FILENAME: f"{filename.split('/')[1]}", RESOURCE_TYPE: ResourceType.MOVIE.value}


def handle_card(assets, path_local: str,  app_type: str, assetBundleName: str) -> dict[str, str] | None:

    def get_member_data_from_asset():
        member_data = [
            data
            for data in (
                s46_member_data
                if "sakukoi" in app_type
                else h46_member_data
            )
            if not data[app_type.split("_")[0]] == ""
            and re.search(
                f"{data['gen']+data[app_type.split('_')[0]]}",
                asset_name[0:3]
                if len(asset_name) <= 5
                else asset_name[3:6]
                if 6 <= len(asset_name) <= 10
                else "000",
            )
        ]
        return member_data

    def get_folder_path(app_type: str):
        folder_path = (
            os.path.join(
                path_local,
                f"{member_data[0]['gen']}{member_data[0][app_type]}. {member_data[0]['name']}",
            )
            if member_data
            else os.path.join(path_local, "00. 不特定")
        )
        return folder_path

    for asset in assets.objects:
        if asset.type.name != "Texture2D":
            continue

        asset_name = asset.read().name

        matcher = (
            r"(^\d{7}_|^\d{3}$|^\d{3}_)"
            if app_type == "sakukoi"
            else r"(^\d{8}_\d|^\d{3}_\d$)"
        )

        if re.match(matcher, asset_name):
            member_data = get_member_data_from_asset()

            # if member_data and (member_data[0]["gen"] == "1" or member_data[0]["gen"] == "2"):
            #     print(f"skip gen 1,2 {asset_name}")
            #     return {FILENAME: asset_name, RESOURCE_TYPE: ResourceType.CARD.value}

            folder_path = get_folder_path(app_type)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

            print(f"save {asset_name} to {folder_path}")

            filename = os.path.join(folder_path, f"{asset_name}.png")
            file_exists = os.path.exists(filename)
            if file_exists:
                print(
                    f"\x1b[38;5;11m{filename} already exist\x1b[0m"
                )
                filename = os.path.join(
                    folder_path, f"{asset_name}-{assetBundleName.split('/')[-1]}.png")
                print(f"rename to {filename}")
                file_exists = os.path.exists(filename)

            if file_exists:
                print(
                    f"\x1b[38;5;11m{filename} still exist after rename... skip this file\x1b[0m"
                )
                continue

            asset.read().image.save(
                os.path.join(folder_path, filename)
            )
            print(f"{asset_name} saved!")
            return {FILENAME: asset_name, RESOURCE_TYPE: ResourceType.CARD.value}


def get_downloaded_dict(download_log_file_name: str) -> dict[str, str]:
    with open(f"{download_log_folder}/{download_log_file_name}", "r") as file:
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


def create_download_log_files(name: str):
    folder = download_log_folder
    if not os.path.exists(folder):
        os.makedirs(folder)
    filename = f"{folder}/{name}"
    if not os.path.exists(filename):
        with open(filename, "w") as file:
            pass
