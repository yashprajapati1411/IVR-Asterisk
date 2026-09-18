import socket
import hashlib
import re

def md5(s):
    return hashlib.md5(s.encode()).hexdigest()

def test_reg():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', 5060))

    reg1 = (
        'REGISTER sip:127.0.0.1 SIP/2.0\r\n'
        'Via: SIP/2.0/TCP 127.0.0.1:5060;branch=z9hG4bK-test1\r\n'
        'From: <sip:100@127.0.0.1>;tag=tag1\r\n'
        'To: <sip:100@127.0.0.1>\r\n'
        'Call-ID: callid1@127.0.0.1\r\n'
        'CSeq: 1 REGISTER\r\n'
        'Contact: <sip:100@127.0.0.1:5060;transport=tcp>\r\n'
        'Expires: 300\r\n'
        'Content-Length: 0\r\n\r\n'
    )
    s.sendall(reg1.encode())
    resp1 = s.recv(2048).decode()
    print('--- Step 1 Response ---')
    print(resp1)

    nonce = re.search(r'nonce="([^"]+)"', resp1).group(1)
    realm = re.search(r'realm="([^"]+)"', resp1).group(1)
    qop = 'auth'
    uri = 'sip:127.0.0.1'
    nc = '00000001'
    cnonce = '0a4f113b'

    ha1 = md5(f'100:{realm}:secretpassword123')
    ha2 = md5(f'REGISTER:{uri}')
    response = md5(f'{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}')

    auth_hdr = (
        f'Digest username="100", realm="{realm}", nonce="{nonce}", '
        f'uri="{uri}", response="{response}", algorithm=MD5, cnonce="{cnonce}", '
        f'qop={qop}, nc={nc}'
    )

    reg2 = (
        'REGISTER sip:127.0.0.1 SIP/2.0\r\n'
        'Via: SIP/2.0/TCP 127.0.0.1:5060;branch=z9hG4bK-test2\r\n'
        'From: <sip:100@127.0.0.1>;tag=tag1\r\n'
        'To: <sip:100@127.0.0.1>\r\n'
        'Call-ID: callid1@127.0.0.1\r\n'
        'CSeq: 2 REGISTER\r\n'
        f'Authorization: {auth_hdr}\r\n'
        'Contact: <sip:100@127.0.0.1:5060;transport=tcp>\r\n'
        'Expires: 300\r\n'
        'Content-Length: 0\r\n\r\n'
    )
    s.sendall(reg2.encode())
    resp2 = s.recv(2048).decode()
    print('--- Step 2 Response ---')
    print(resp2)

if __name__ == "__main__":
    test_reg()
