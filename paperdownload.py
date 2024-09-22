import requests
from lxml import etree
import os
from tqdm import tqdm
from contextlib import closing
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class SciHubDownloader:
    def __init__(self, doi_list_file, download_path, proxy=None, xpath='//embed[@type="application/pdf"]/@src', sci_hub_urls=None):
        """
        初始化SciHubDownloader类，设置DOI列表文件、下载路径、代理和Sci-Hub的URL
        """
        self.doi_list_file = doi_list_file
        self.download_path = download_path
        self.proxy = proxy
        self.xpath = xpath
        self.scihub_urls = sci_hub_urls if sci_hub_urls else ["https://sci-hub.se/", "https://sci-hub.st/"]
        self.doilist = self.load_doi_list()
        self.session = self.create_session_with_retry()

        # 确保下载路径存在
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

    def load_doi_list(self):
        """
        从DOI列表文件加载DOI
        """
        with open(self.doi_list_file, 'r') as f:
            return [doi.strip() for doi in f.readlines()]

    def create_session_with_retry(self, retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504)):
        """
        创建带有重试机制的requests session
        """
        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def ensure_scheme(self, url):
        """
        确保URL以 'https://' 开头
        """
        if not url.startswith('http'):
            return 'https:' + url
        return url

    def sanitize_filename(self, doi):
        """
        清理文件名中的非法字符
        """
        return re.sub(r'[\/:*?"<>|]', '_', doi) + ".pdf"

    def get_file_size(self, req_file, index, total):
        """
        获取文件大小并返回
        """
        try:
            content_length = int(req_file.headers['content-length'])
            print(f"Downloading paper {index+1}/{total}, size: {content_length/1024:.2f} KB")
            return content_length
        except KeyError:
            print(f"Downloading paper {index+1}/{total}, size: unknown")
            return None

    def download(self, index, doi):
        """
        根据DOI从Sci-Hub下载论文
        """
        for scihub_url in self.scihub_urls:
            try:
                # 获取网页内容
                req = self.session.get(url=scihub_url + doi, proxies=self.proxy)

                if req.status_code != 200:
                    print(f"Error downloading {doi}: Failed to fetch the webpage from {scihub_url}, status code: {req.status_code}")
                    continue  # 尝试下一个URL

                # 解析HTML内容
                root = etree.HTML(req.content)
                if root is None:
                    print(f"Error downloading {doi}: Failed to parse HTML content")
                    return

                # 获取下载链接
                element_download_link = root.xpath(self.xpath)
                if not element_download_link:
                    print(f"Error downloading {doi}: No download link found")
                    return

                # 确保URL有 https:// 前缀
                element_download_link = self.ensure_scheme(element_download_link[0])

                # 下载文件
                req_file = self.session.get(url=element_download_link, stream=True, proxies=self.proxy)
                if req_file.status_code != 200:
                    print(f"Error downloading {doi}: Failed to retrieve file, status code: {req_file.status_code}")
                    return

                # 获取文件大小
                content_length = self.get_file_size(req_file, index, len(self.doilist))
                file_name = self.sanitize_filename(doi)

                # 保存文件
                with closing(req_file) as response:
                    chunk_size = 1024
                    file_path = os.path.join(self.download_path, file_name)
                    with open(file_path, "wb") as file:
                        with tqdm(total=content_length, unit='B', unit_scale=True, desc=file_name, leave=False) as pbar:
                            for chunk in response.iter_content(chunk_size=chunk_size):
                                if chunk:  # 过滤掉 keep-alive 空数据块
                                    file.write(chunk)
                                    pbar.update(len(chunk))
                print(f"Downloaded {file_name} successfully!")
                return

            except Exception as e:
                print(f"Error downloading {doi} from {scihub_url}: {str(e)}")
                with open("errlog.txt", "a") as err_log:
                    err_log.write(f"{doi} from {scihub_url} - {str(e)}\n")
        print(f"Failed to download {doi} after trying all Sci-Hub URLs.")

    def run(self):
        """
        遍历DOI列表并下载
        """
        for index, doi in enumerate(self.doilist):
            print(f"Starting download for DOI: {doi}")
            self.download(index, doi)

if __name__ == "__main__":
    
    downloader = SciHubDownloader(
        doi_list_file="D:/vscode/pysapce/doi_list.txt",  # DOI列表文件路径
        download_path="D:/vscode/pysapce/downloads",     # 文件保存路径
        proxy=None  # 如果需要代理，在此添加
    )
    downloader.run()
