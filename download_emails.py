import imaplib
from email.parser import BytesParser
from pprint import pprint
import email.header
import time
import json
import csv

# Settings
username = 'put your email username here i.e. user@gmail.com'
password = 'password here'

# path to ouput file name (leave off the extention)
ouput_filename = '/Users/gjenkins/Desktop/all_email' # output of all data, note extension is on next variable
output_type = 'json' # any other setitng will output csv to the extention

imapAddress = 'imap.gmail.com'

column_names = [ 'n', 'From','To','Subject','Date','Received', 'Rfc822msgid','Size','uid',
                 'Attachments', 'text/plain','text/html',]

chunk = 1000 # number emails to ask for at each fetch imap server
start = 0 # start from first message
endAt = 50 # None # set to last number or None to get all email account

def f_recieved(s): return { 'Rfc822msgid': f'Rfc822msgid:{s}'}; # just past this into gmail to find message

# specify header parts to save and any conversion functions on them
key_map = { 'From':None, 'To':None, 'Subject':None, 'Date':None,
            'Received': None, 'Message-ID':f_recieved, }

def parse_parts(msg, key_map):
    ''' return {key:msg[header_key]} or {parse_fun(msg[header_key]) as instructed in keymap'''
    parts = {}
    for hkey in key_map:
        raw = msg[hkey]
        if raw:
            if isinstance(raw, email.header.Header): raw = str(raw) # to fix non ascii parts
            f = key_map[hkey]
            if f:
                fparts = f(raw)
                for k in fparts: parts[k] = fparts[k]
            else: parts[hkey] = raw
    return parts

def decode_part(part, mime_type): # decode a part from the correct char coding. This was tricky
    charset = part.get_content_charset()
    if part.get_content_type() == mime_type:
        part_str = part.get_payload(decode=1)
        if charset == None: # this is when the coding is not in the email data
            charset = 'utf-8' # assume utf-8 then
        try:
            return part_str.decode(charset, 'replace') # and try with replacement
        except:
            # on fail, ouput the message id in form that works with gmail find box
            print(f"** pos {pos} {parts['Rfc822msgid']}:Decode Error, {mime_type} part skipped")
            pprint(part_str) # and print what caused the error
            print('----------')
            return "" # no part if error
    return ""


def decode_email(msg_str, pos, key_map): # process whole email parts and build email list/dict records
    filenames = None
    p = BytesParser()
    message = p.parsebytes(msg_str)  # get header
    parts = parse_parts(message, key_map) # add header parts specified in key_map
    parts['Size'] = len(msg_str)
    plain_body = ''
    html_body = ''
    for part in message.walk():

        plain_body += decode_part(part, 'text/plain')
        if len(plain_body) > 0:
            html_body = ""
        else:
            html_body += decode_part(part, 'text/html')

        fn = part.get_filename()
        if fn:
            if filenames == None: filenames = []
            filenames.append(fn)
    if filenames:
        parts['Attachments'] = filenames
    if len(plain_body) > 0:
        parts['text/plain'] = plain_body
    elif len(html_body) > 0:
        parts['text/html'] = html_body
    return parts


def store_json(file, recs):
    with open(file + '.json','w') as f:
        f.write(json.dumps(recs, sort_keys=True, indent=4))


def store_csv(file, recs):
    with open(file + '.csv', 'w') as f:
        dict_writer = csv.DictWriter(f, column_names)
        dict_writer.writeheader()
        dict_writer.writerows(recs)


if __name__ == '__main__':

    t0 = time.time()
    ms = imaplib.IMAP4_SSL(imapAddress) # open imap session ms
    ms.login(username, password)
    if ms.state == "AUTH":
        print("logged in OK")
    else:
        print("login Failed")
        exit(1)

    ms.select('"[Gmail]/All Mail"') # select all mail folders, this is specific to gmail!
    # NOTE: the double quotes are part of the select

    result, data = ms.uid('search', None, 'ALL') # return 1 to number of all emails, list of uids
    uids = data[0].split() # parse into array
    n = len(uids) # get number of all emails

    if endAt: n = endAt # override nif endAt is set

    recs = []
    for i in range(start,n,chunk): # fetch 250 emails each time
        srange = f'{i+1}:{min(i+chunk,n)}'
        resp,data = ms.fetch(srange , '(RFC822)')

        for id,msg in enumerate((m[1] for m in data if isinstance(m,tuple))):
            pos = i + id + 1
            parts = decode_email(msg, pos, key_map)
            pos = i + id + 1
            parts['uid'] = str(int(uids[pos - 1]))
            parts['n'] = pos
            recs.append(parts)
            try:
                json.dumps(parts)
            except:
                print(f"** pos {pos} {parts['Rfc822msgid']}:json dump fail") # catch some rare errors here
                pprint(parts)
                print('---------')

        t1 = time.time()
        elapsed_mins = (t1 - t0)/60 # mins from start

        print(f'@ {pos}/{n} {pos/n*100:.1f}% elapsed: {elapsed_mins:.2f} mins')

    ms.logout()

    if output_type == 'json':
        store_json(ouput_filename, recs)
    else:
        store_csv(ouput_filename, recs)

    print('*** DONE ***')
