import json
import os,sys,platform,time
import re
import lxml
import lxml.html
import lxml.etree
import html
import urllib.parse
from collections import OrderedDict
from collections import Mapping
from xmljson import BadgerFish

import io

def getResourceFolder():
    if getattr(sys, 'frozen', False) and (platform.system() != 'Darwin'):
        folder = os.path.dirname(sys.executable)
    elif getattr(sys, 'frozen', False) and (platform.system() == 'Darwin'):
        folder = sys._MEIPASS
    else:
        folder = os.getcwd()

    return folder

def hasDictValue(data,multikey, piped=False):
    try:
        multikey = multikey.split('|').pop(0) if piped else multikey

        keys=multikey.split('.',1)

        if isinstance(data, Mapping) and keys[0] != '':

            if len(keys) > 1:
                value = data.get(keys[0],"")
                value = hasDictValue(value,keys[1])
            else:
                value = keys[0] in data

            if (not value) and (keys[0] == '*'):
                if len(keys) == 1:
                    value = bool(data)

                else:
                    listkey = keys[1]
                    for elem in data:
                        value = hasDictValue(data[elem], listkey)
                        if value:
                            break

        elif type(data) is list and keys[0] == '*':
            if len(keys) > 1 and len(data) > 0:
                value = data[0]
                value = hasDictValue(value,keys[1])
            else:
                value = len(data) > 0
        elif type(data) is list and keys[0].isnumeric():
            no = int(keys[0])
            if len(keys) > 1 and len(data) > no:
                value = data[no]
                value = hasDictValue(value,keys[1])
            else:
                value = len(data) > no

        else:
            value = False

        return value

    except Exception as e:
        return False


def extractValue(data, multikey, dump=True):
    """Extract value from dict and pipe through modifiers
    :param data:
    :param multikey:
    :param dump:
    :return:
    """
    try:
        pipeline = multikey.split('|')
        multikey = pipeline.pop(0)

        # Input: dict. Output: string, number, list or dict
        value = getDictValue(data, multikey, dump)

        for idx, modifier in enumerate(pipeline):
            value = value if type(value) is list else [value]

            if modifier.startswith('json:'):
                # Input: list of strings.
                # Output if dump==True: list of strings
                # Output if dump==False: list of dict, list, string or number
                selector = modifier[5:]


                # Flatten list if not dumped
                if dump:
                    value = [getDictValue(json.loads(x), selector, dump=dump) for x in value]
                else:
                    items = [getDictValue(json.loads(x), selector, dump=dump) for x in value]
                    value = []
                    for item in items:
                        if type(item) is list:
                            value += item
                        else:
                            value.append(item)

            elif modifier.startswith('css:'):
                # Input: list of strings.
                # Output: list of strings
                selector = modifier[4:]
                value = [extractHtml(x, selector, type='css') for x in value]
                value = [y for x in value for y in x]
            elif modifier.startswith('xpath:'):
                # Input: list of strings.
                # Output: list of strings
                selector = modifier[6:]
                value = [extractHtml(x, selector, type='xpath') for x in value]
                value = [y for x in value for y in x]

        # If modified in pipeline (otherwise already handled by getDictValue)...
        if dump and (type(value) is dict):
            value = json.dumps(value)
        if dump and (type(value) is list):
            value = ";".join(value)
        elif dump and (isinstance(value, int)):
            value = str(value)

        return value

    except Exception as e:
        return ""

def getDictValue(data, multikey, dump=True):
    """Extract value from dict
    :param data:
    :param multikey:
    :param dump:
    :return:
    """
    try:
        keys=multikey.split('.',1)

        if isinstance(data, Mapping) and keys[0] != '':
            try:
                value=data[keys[0]]
                if len(keys) > 1:
                    value = getDictValue(value,keys[1],dump)
            except:
                if keys[0] == '*':
                    listkey = keys[1] if len(keys) > 1 else ''
                    value=[]
                    for elem in data:
                        value.append(getDictValue(data[elem],listkey,dump))
                else:
                    value = ''

        elif type(data) is list and keys[0] != '':
            try:
                value=data[int(keys[0])]
                if len(keys) > 1:
                    value = getDictValue(value,keys[1],dump)
            except:
                if keys[0] == '*':
                    listkey = keys[1] if len(keys) > 1 else ''
                else:
                    listkey = keys[0]

                value=[]
                for elem in data:
                    value.append(getDictValue(elem, listkey, dump))

        else:
            value = data

        if dump and (type(value) is dict):
            value = json.dumps(value)
        elif dump and (type(value) is list):
            value = ";".join(value)
        elif dump and (isinstance(value, int)):
            value = str(value)
        elif dump and (isinstance(value, float)):
            value = str(value)

        return value

    except Exception as e:
        return ""

def filterDictValue(data, multikey, dump=True, piped=False):
    try:
        multikey = multikey.split('|').pop(0) if piped else multikey
        keys=multikey.split('.',1)

        if isinstance(data, Mapping) and keys[0] != '':
            value = { key: data[key] for key in list(data.keys()) if key != keys[0]}
            if len(keys) > 1:
                value[keys[0]] = filterDictValue(data[keys[0]],keys[1],False)
            if not len(value):
                value = None

        elif type(data) is list and keys[0] != '':
            try:
                value=data
                if len(keys) > 1:
                    value[int(keys[0])] = getDictValue(value[int(keys[0])],keys[1],False)
                else:
                    value[int(keys[0])] = ''
            except:
                if keys[0] == '*' and len(keys) > 1:
                    listkey = keys[1]
                elif keys[0] == '*':
                    listkey = ''
                else:
                    listkey = keys[0]

                valuelist=[]
                for elem in data:
                    valuelist.append(filterDictValue(elem,listkey,False))
                value = valuelist

        else:
            value = ''


        if dump and (type(value) is dict or type(value) is list):
            return json.dumps(value)
        else:
            return value

    except Exception as e:
        return ""

def recursiveIterKeys(value,prefix=None):
    for key in value.keys():
        if type(value[key]) is dict:
            for subkey in recursiveIterKeys(value[key],key):
                fullkey = subkey if prefix is None else ".".join([prefix,subkey])
                yield fullkey
        else:
            fullkey = key if prefix is None else ".".join([prefix,key])
            yield fullkey

def htmlToJson(data,csskey=None,type='lxml'):
    #type='html5'
    soup = lxml.html.fromstring(data)

    def parseSoup(element,context = True):
        out = {}
        if context:
            #out['name'] = element.tag
            if element.text is not None:
                out['text'] = str(element.text).strip("\n\t ")
                
        attributes= {}
        if context:                
            for name, value in sorted(element.items()):
                attributes['@'+name] = value
        out.update(attributes)
                        
        children = []
        for child in element:
            if isinstance(child.tag, str):
                id = str(child.get('id',''))
                key = child.tag+'#'+id if id != '' else child.tag
                children.append({key:parseSoup(child)})
            else:
                value = str(child.text).strip("\n\t ")
                if value != '':
                    children.append({'text':value})

        if len(children) > 0:
            out['items'] = children
        
        #simplify:
        if len(children) == 0 and len(attributes) ==0:
            out = out.get('text',None)
        elif len(children) > 0 and len(attributes) ==0 and out.get('text',None) is None:
            del out['items']
            out = children
            
        return out

    output = []
    if csskey is not None:
        for part in soup.cssselect(csskey):
            output.append(parseSoup(part,True))
    else:
        output = {soup.tag : parseSoup(soup,True)}

    return output


def elementToJson(element, context=True):
    out = {}
    if context:
        out['tag'] = element.tag
        out['text'] = element.text_content().strip("\r\n\t ")
        #if element.text is not None:
        #    out['text'] = str(element.text).strip("\n\t ")

    attributes = {}
    if context:
        for name, value in sorted(element.items()):
            attributes['@' + name] = value
    out.update(attributes)

    # children = []
    # for child in element:
    #     if isinstance(child.tag, str):
    #         id = str(child.get('id', ''))
    #         key = child.tag + '#' + id if id != '' else child.tag
    #         children.append({key: parseSoup(child)})
    #     else:
    #         value = str(child.text).strip("\n\t ")
    #         if value != '':
    #             children.append({'text': value})
    #
    # if len(children) > 0:
    #     out['items'] = children

    # simplify:
    # if len(children) == 0 and len(attributes) == 0:
    #     out = out.get('text', None)
    # elif len(children) > 0 and len(attributes) == 0 and out.get('text', None) is None:
    #     del out['items']
    #     out = children

    return out



def extractLinks(data,baseurl):
    links = []
    soup = lxml.html.fromstring(data)

    base = soup.find('base')
    base = base.get('href') if base is not None else None
    baseurl = urllib.parse.urljoin(baseurl,base)

    for part in soup.cssselect('a'):
        link = elementToJson(part, True)
        if link.get('@href',None) is not None:
            link['url'] = urllib.parse.urljoin(baseurl, link.get('@href',None))
        links.append(link)

    return links, base

def extractHtml(html, selector, type='css', dump=False):
    items = []

    if html != '':
        try:
            soup = lxml.html.fromstring(html)

            if type == 'css':
                for item in soup.cssselect(selector):
                    item = lxml.etree.tostring(item).decode('utf-8').strip()
                    items.append(item)
            elif type == 'xpath':
                result = soup.xpath(selector)
                result = result if isinstance(result, list) else [result]
                for item in result:
                    if isinstance(item,lxml.etree._Element):
                        item = lxml.etree.tostring(item).decode('utf-8')
                    items.append(str(item).strip())

        except Exception as e:
            items.append('ERROR: '+str(e))

    return items

def xmlToJson(data):
    bf = BadgerFish(dict_type=OrderedDict)
    xml = lxml.html.fromstring(data)
    data = bf.data(xml)
    return data


def makefilename(url = None, foldername=None, filename=None, fileext=None, appendtime=False):  # Create file name
    url_filename, url_fileext = os.path.splitext(os.path.basename(url))
    if fileext is None:
        fileext = url_fileext
    if filename is None:
        filename = url_filename

    filename = re.sub(r'[^a-zA-Z0-9_.-]+', '', filename)
    fileext = re.sub(r'[^a-zA-Z0-9_.-]+', '', fileext)

    filetime = time.strftime("%Y-%m-%d-%H-%M-%S")
    filenumber = 0

    while True:
        newfilename = filename[:100]
        if appendtime:
            newfilename += '.' + filetime
        if filenumber > 0:
            newfilename += '-' + str(filenumber)

        newfilename += str(fileext)
        fullfilename = os.path.join(foldername, newfilename)

        if (os.path.isfile(fullfilename)):
            filenumber = filenumber + 1
        else:
            break

    return fullfilename


# See http://foobarnbaz.com/2012/12/31/file-upload-progressbar-in-pyqt/
# See http://code.activestate.com/recipes/578669-wrap-a-string-in-a-file-like-object-that-calls-a-u/
class CancelledError(Exception):
    """Error denoting user interruption.
    """
    def __init__(self, msg):
        self.msg = msg
        Exception.__init__(self, msg)

    def __str__(self):
        return self.msg

    __repr__ = __str__


class BufferReader():
    """StringIO with a callback.
    """
    def __init__(self, data='',callback=None):
        self._callback = callback
        self._progress = 0
        self._len = int(len(data))

        if type(data) == str:
            data = data.encode()

        self._io = io.BytesIO(data)

    def __len__(self):
        return self._len
    
    def rewind(self):
        self._io.seek(0)
        
    def read(self, *args):
        chunk = self._io.read(*args)
        self._progress += int(len(chunk))
        if self._callback:
            try:
                self._callback(self._progress,self._len)
            except:
                raise CancelledError('The upload was cancelled.')

        return chunk

def wraptip(value):
    try:
        value = '<qt>{}</qt>'.format(html.escape(str(value))) if value is not None else value
    except:
        pass
    return value

def formatdict(data):
    def getdictvalues(data, parentkeys = []):
        out = []
        for key, value in data.items():
            if isinstance(value, Mapping):
                children = getdictvalues(value, parentkeys + [key])
                out.extend(children)
            else:
                child = ".".join(parentkeys + [key]) + " = " + str(value)
                child= "<p>"+wraptip(child)+"</p>"
                out.extend([child])
        return out

    return "\n".join(getdictvalues(data))

