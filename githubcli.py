import requests
from bs4 import BeautifulSoup
from utils import get_file_size

import mimetypes
import uuid

import requests_toolbelt as rt
from requests_toolbelt import MultipartEncoderMonitor
from requests_toolbelt import MultipartEncoder
from functools import partial

import json
import re
import time

class CallingUpload:
                def __init__(self, func,filename,args):
                    self.func = func
                    self.args = args
                    self.filename = filename
                    self.time_start = time.time()
                    self.time_total = 0
                    self.speed = 0
                    self.last_read_byte = 0
                def __call__(self,monitor):
                    self.speed += monitor.bytes_read - self.last_read_byte
                    self.last_read_byte = monitor.bytes_read
                    tcurrent = time.time() - self.time_start
                    self.time_total += tcurrent
                    self.time_start = time.time()
                    if self.time_total>=1:
                            clock_time = (monitor.len - monitor.bytes_read) / (self.speed)
                            if self.func:
                                 self.func(self.filename,monitor.bytes_read,monitor.len,self.speed,clock_time,self.args)
                            self.time_total = 0
                            self.speed = 0

class GithubCli(object):
    def __init__(self, username='',password='',my='Obysoft2020'):
        self.host = 'https://github.com/'
        self.hosting = 'https://github.com'
        self.nexushost = 'https://nexus.uclv.edu.cu/repository/'
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.my = my

    def get_login_data(self):
        headers = {
         'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'
        }
        resp = self.session.get(self.host+'login',headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        authenticity_token = soup.find('input',{'name':'authenticity_token'})['value']
        timestamp_secret = soup.find('input',{'name':'timestamp_secret'})['value']
        timestamp = soup.find('input',{'name':'timestamp'})['value']
        inputs = soup.find_all('input')
        random = ''
        for i in inputs:
            if 'required_field_' in i['name']:
                random = i['name']
                break
        return authenticity_token,timestamp, timestamp_secret,random

    def login(self):
        authenticity_token,timestamp,timestamp_secret,random = self.get_login_data()
        headers = {
         'Content-Type':'application/x-www-form-urlencoded',
         'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'
        }
        data = {
            'commit': 'Sign+in',
            'authenticity_token': authenticity_token,
            'login': self.username,
            'password': self.password,
            'trusted_device':'',
            'webauthn-support': 'upported',
            'webauthn-iuvpaa-support': 'unsupported',
            'return_to':self.host+'login',
            'allow_signup':'',
            'client_id':'',
            'integration':'',
            'timestamp':timestamp,
            'timestamp_secret': timestamp_secret
        }
        if random!='':
            data[random] = ''
        resp = self.session.post(self.host+'session', data=data,headers=headers)
        resp = self.session.get(self.host+self.my,headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        title = soup.find('title').next
        # Sentencia, si el nombre de usuario existe, el inicio de sesión es exitoso, de lo contrario el inicio de sesión falla
        if title==self.my:
            return True

        return False


    def upload_file(self,file,progresscallback=None,args=None,user='obisoftdev'):
        try:
            gettokendataurl = f'{self.host}{self.my}/{user}-upload/upload'
            resp = self.session.get(gettokendataurl)
            soup = BeautifulSoup(resp.text, 'html.parser')
            formauth = soup.find('form',{'action':'/upload/manifests'})
            formcommit = soup.find_all('form',{'action':f'/{self.my}/{user}-upload/upload'})[-1]
            token = formauth.find('input',{'name':'authenticity_token'})['value']
            token_commit = formcommit.find('input',{'name':'authenticity_token'})['value']
            repoid = soup.find('input',{'name':'repository_id'})['value']

            # requests get manifest_repo_id
            manifestpaylod = {'authenticity_token':(None,token),
                              'repository_id':(None,repoid),
                              'directory_binary':(None,'')}
            b = uuid.uuid4().hex
            encoder = rt.MultipartEncoder(manifestpaylod)
            monitor = MultipartEncoderMonitor(encoder,callback=None)
            manifesturl = f'{self.host}upload/manifests'
            headers = {'Accept':'application/json',
                       "Content-Type": monitor.content_type}
            resp = self.session.post(manifesturl,data=monitor,headers=headers)
            jsondata = json.loads(resp.text)
            manifestid = jsondata['upload_manifest']['id']
            #end

            mimetype = mimetypes.MimeTypes().guess_type(file)[0]

            if not mimetype:
                mimetype = 'application/octet-stream'

            # requests get data for upload
            getdataurl = f'{self.host}upload/policies/upload-manifest-files'
            token = soup.find('input',{'class':'js-data-upload-policy-url-csrf'})['value']
            payload = {'name':(None,file),
                       'size':(None,str(get_file_size(file))),
                       'content_type':(None,mimetype),
                       'authenticity_token':(None,token),
                       'repository_id':(None,str(repoid)),
                       'upload_manifest_id':(None,str(manifestid))}
            b = uuid.uuid4().hex
            encoder = rt.MultipartEncoder(payload)
            monitor = MultipartEncoderMonitor(encoder,callback=None)
            headers = {'Accept':'application/json',
                       "Content-Type": monitor.content_type}
            resp = self.session.post(getdataurl,data=monitor,headers=headers)
            jsondata = json.loads(resp.text)
            #end

            # requests upload file
            uploadurl = jsondata['upload_url']
            of = open(file,'rb')
            upload_data = {'key':(None,jsondata['form']['key']),
                       'acl':(None,jsondata['form']['acl']),
                       'policy':(None,jsondata['form']['policy']),
                       'X-Amz-Algorithm':(None,jsondata['form']['X-Amz-Algorithm']),
                       'X-Amz-Credential':(None,jsondata['form']['X-Amz-Credential']),
                       'X-Amz-Date':(None,jsondata['form']['X-Amz-Date']),
                       'X-Amz-Signature':(None,jsondata['form']['X-Amz-Signature']),
                       'Content-Type':(None,mimetype),
                       'file':(file,of,mimetype)}
            b = uuid.uuid4().hex
            encoder = rt.MultipartEncoder(upload_data)
            progrescall = CallingUpload(progresscallback,file,args)
            callback = partial(progrescall)
            monitor = MultipartEncoderMonitor(encoder,callback=callback)
            headers = {"Content-Type": monitor.content_type}
            resp = requests.post(uploadurl,data=monitor,headers=headers)
            of.close()
            #end

            # requests put file
            putfileurl = str(self.hosting) + jsondata['asset_upload_url']
            upload_data = {'authenticity_token':(None,jsondata['asset_upload_authenticity_token'])}
            encoder = rt.MultipartEncoder(upload_data)
            monitor = MultipartEncoderMonitor(encoder,callback=None)
            headers = {'Accept':'application/json',
                       "Content-Type": monitor.content_type}
            resp = self.session.put(putfileurl,data=monitor,headers=headers)
            jsondata = json.loads(resp.text)
            #end

            commit_payload = {'authenticity_token':token_commit,
                              'message':'',
                              'description':'',
                              'commit-choice':'direct',
                              'target_branch':'main',
                              'quick_pull':'main',
                              'manifest_id':str(manifestid)}
            resp = self.session.post(gettokendataurl,data=commit_payload)

            if resp.status_code == 200:
                url = f'{self.host}{self.my}/{user}-upload/raw/main/' + file
                url = str(url).replace('https://','')
                url = self.nexushost + url
                return {'name':file,'url':url}
        except Exception as ex:
            print(str(ex))
            pass
        return None

#cli = GithubCli('obysoft2001@gmail.com','Obysoft2001@')
#loged = cli.login()
#if loged:
#   print('Loged!')
#   data = cli.upload_file('requirements.txt')