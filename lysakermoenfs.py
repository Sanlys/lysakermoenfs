import os
import sys
from fuse import FUSE, FuseOSError, Operations
import errno
from bs4 import BeautifulSoup
import requests
import re
from datetime import datetime

def handle_special_cases(path):
    if path == "/":
        return dict(st_mode=(0o040000 | 0o555), st_nlink=2)
    if path == "/.":
        return dict(st_mode=(0o040000 | 0o555), st_nlink=2)
    if path == "/..":
        return dict(st_mode=(0o040000 | 0o555), st_nlink=2)
    if path == "./":
        return dict(st_mode=(0o040000 | 0o555), st_nlink=2)
    if path == "../":
        return dict(st_mode=(0o040000 | 0o555), st_nlink=2)
    return None

def fetch_entries_from_web(parentPath):
    output = [
        {
            "name": "..",
            "size": "-",
            "is_directory": True,
            "last_updated": 0
        },
        {
            "name": ".",
            "size": "-",
            "is_directory": True,
            "last_updated": 0
        }
    ]
    response = requests.get("https://lysakermoen.com"+parentPath)
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a')
    for link in links:
        fileObject = {}
        clean_sibling = link.next_sibling.strip()
        clean_sibling = re.sub(' +', ' ', clean_sibling)
        if clean_sibling == '':
            continue
        datestring, fileSize = re.match(r'^(\d\d-[A-Z][a-z]{2}-\d\d\d\d \d\d:\d\d) ([0-9-]+)$', clean_sibling).groups()
        fileObject["name"] = re.match(r'([^\/]+)', link.get('href')).groups()[0]
        fileObject["size"] = int(fileSize) if isinstance(fileSize, (int, float, str)) and str(fileSize).isdigit() else fileSize
        fileObject["is_directory"] = bool(re.search(r'/$', link.get('href')))
        fileObject["last_updated"] = int(datetime.strptime(datestring, "%d-%b-%Y %H:%M").timestamp())
        output.append(fileObject)
    return output

def find_matching_entry(entries, entryname):
    for entry in entries:
        if entry["name"] == entryname:
            return entry
    
    return None
    
def build_result(matching_entry):
    if matching_entry["is_directory"]:
        return dict(st_mode=(0o040000 | 0o555), st_nlink=2, st_mtime=matching_entry["last_updated"])
    else:
        return dict(st_mode=(0o100000 | 0o444), st_nlink=1, st_size=matching_entry["size"], st_mtime=matching_entry["last_updated"])

class WebDirectoryFS(Operations):
    def __init__(self):
        self.entriesFromWeb = []
        self.entriesFromWebPath = ""

    def getattr(self, path, fh=None):
        result = handle_special_cases(path)
        if result:
            return result

        parentPath = os.path.dirname(path)
        if parentPath != self.entriesFromWeb:
            self.entriesFromWeb = fetch_entries_from_web(parentPath)
            self.entriesFromWebPath = parentPath
        entryname = os.path.basename(path)
        matching_entry = find_matching_entry(self.entriesFromWeb, entryname)
        
        if matching_entry is None:
            raise FuseOSError(errno.ENOENT)

        return build_result(matching_entry)
    

    def readdir(self, path, fh):
        entries = []
        # Exclude '..' if in the root directory
        special_entries = ['.'] if path == '/' else ['.', '..']
        for link in BeautifulSoup(requests.get("https://lysakermoen.com" + path).text, 'html.parser').find_all('a'):
            entries.append(link.get('href').replace("/", ""))
        return special_entries + list(set(entries) - {'.', '..'})


    def open(self, path, flags):
        return 0

    def read(self, path, length, offset, fh):
        print("Reading partial file")
        url = "https://lysakermoen.com" + path
        headers = {'Range': f'bytes={offset}-{offset+length-1}'}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 206 or response.status_code == 200:
            return response.content
        else:
            raise FuseOSError(errno.ENOENT)


def main(mountpoint):
    FUSE(WebDirectoryFS(), mountpoint, nothreads=True, foreground=True, ro=True)

if __name__ == '__main__':
    main(sys.argv[1])