import re
from sgmllib import SGMLParser
from datetime import date
from common import (
    BaseBrowser,
    open_file,
    )


class SaldoParser(SGMLParser):
    def __init__(self):
        SGMLParser.__init__(self)
        self.tag_b = False
        self.catat = False
        self.data = [] 
        self.baris = []
        self.hasil = []

    def start_tr(self, attrs):
        pass

    def end_tr(self):
        if self.baris:
            self.hasil.append( self.baris )
        self.baris = []

    def start_td(self, attrs):
        pass

    def end_td(self):
        if self.data:
            self.baris.append(' '.join(self.data))
        self.data = []

    def start_b(self, attrs):
        self.tag_b = True

    def end_b(self):
        self.tag_b = False
        if self.data:
            pass

    def handle_data(self, data):
        if self.tag_b:
            if data == 'Saldo Efektif':
                self.catat = True
                return
        if not self.catat:
            return
        data = data.strip()
        if not data:
            return
        self.data.append(data)

    def get_clean_data(self):
        r = [] 
        for rek, jenis, mata_uang, nominal  in self.hasil:
            nominal = to_float(nominal)
            r.append((rek, jenis, mata_uang, nominal))
        return r 


POLA = [ 
    # Ainul: kalau ada 95031 berarti mm/dd
    # TRSF E-BANKING CR 01/04 95031 ENOK SUYITNO -> 4 Januari
    [' ([0-9][0-9])/([0-9][0-9]) 95031',2,1],
    # TRSF E-BANKING DB 06/24 79021 DJIJO EKA PUTRA
    [' ([0-9][0-9])/([0-9][0-9]) 79021',2,1],
    # TRSF E-BANKING DB 04/19 79011 IKONPULSA TAJUS SUBKI
    [' ([0-9][0-9])/([0-9][0-9]) 79011',2,1],
    # TRSF E-BANKING DB 07/17 77981 SAMSUNGGGGGGGGGT DESY KRISTINA
    [' ([0-9][0-9])/([0-9][0-9]) 77981',2,1],
    # TRSF E-BANKING DB 08/12 84601 IKON-NOV AHMAD HUSNI
    # TRSF E-BANKING DB TANGGAL NULL/08 08/08  WSID:59611 AHMAD HUSNI
    ['DB ([0-9][0-9])/([0-9][0-9])',1,2],
    # TRSF E-BANKING CR 0706/FTSCY/WS95011 200183.00 ABDUL RAJAB FAJAR
    # TRSF E-BANKING DB 1408/FTSCY/WS95011 300300.00 IKON-NOV AHMAD HUSNI
    ['(DB|CR) ([0-9][0-9])([0-9][0-9])',2,3],
    # SWITCHING CR TANGGAL :07/06    TRANSFER   DR 002 ADITANTRA         0524 - KCP
    [':([0-9][0-9])/([0-9][0-9])',1,2],
    ]


class MutasiParser(SGMLParser):
    def __init__(self):
        SGMLParser.__init__(self)
        self.hasil = []
        self.baris = []
        self.data = []

    def start_tr(self, attrs):
        pass

    def end_tr(self):
        if self.baris:
            self.hasil.append( self.baris )
        self.baris = []

    def start_td(self, attrs):
        pass

    def end_td(self):
        if self.data:
            self.baris.append(' '.join(self.data))
        self.data = []

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return
        self.data.append(data)

    def get_clean_data(self):
        data = []
        for r in self.hasil: 
            if r[0] == 'Nomor Rekening':
                if not r[2:]:
                    return
                rekening = r[2]
            elif r[0] == 'Periode':
                d, m, y = r[2].split('-')[0].strip().split('/')
                tanggal = date(int(y), int(m), int(d))
            elif r[4:] and r[4] in ['CR','DB']:
                tgl, ket, cab, nominal, mutasi, saldo = r
                nominal = to_float(nominal)
                saldo = to_float(saldo)
                if mutasi == 'DB':
                    nominal = - nominal
                if tgl == 'PEND':
                    tgl = tgl_sebenar(ket, tanggal)
                else:
                    d, m = tgl.split('/') # 08/06 -> 8 Juni
                    tgl = date(tanggal.year, int(m), int(d))
                data.append((rekening, tgl, ket, nominal, saldo))
        return data


def to_float(s):
    return float(s.replace(',',''))

def ket2tgl(s):
    for regex, ud, um in POLA:
        match = re.compile(regex).search(s)
        if match:
            return int(match.group(ud)), int(match.group(um))
    return None, None

def tgl_sebenar(ket, tgl_catat):
    d, m = ket2tgl(ket)
    if not d:
        return tgl_catat
    tgl_ket = date(tgl_catat.year, m, d)
    if tgl_ket > tgl_catat and tgl_ket.year == tgl_catat.year:
        tgl_ket = date(tgl_catat.year - 1, m, d)
    jeda = tgl_catat - tgl_ket
    if abs(jeda.days) > 29:
        return date(tgl_catat.year, d, m)
    return tgl_ket


ERR_LOGIN = 'Mohon masukkan User ID/Password Anda yg benar'

class Browser(BaseBrowser):
    def __init__(self, username, password, parser, output_file=None):
        super(Browser, self).__init__('https://ibank.klikbca.com',
            username, password, parser, output_file=output_file)

    def login(self):
        self.open_url()
        self.br.select_form(nr=0)
        self.br['value(user_id)'] = self.username 
        self.br['value(pswd)'] = self.password 
        self.info('Login %s' % self.username)
        resp = self.br.submit(name='value(Submit)', label='LOGIN')
        content = resp.read()
        if content.find(ERR_LOGIN) > -1:
            self.last_error = ERR_LOGIN 
        else:
            return True

    def logout(self):
        self.open_url('/authentication.do?value(actions)=logout')


class SaldoBrowser(Browser):
    def __init__(self, username, password, output_file=None):
        Browser.__init__(self, username, password, SaldoParser, output_file)

    def browse(self):
        return self.open_url('/balanceinquiry.do', {}) # POST


class MutasiBrowser(Browser):
    def __init__(self, username, password, output_file=None):
        Browser.__init__(self, username, password, MutasiParser, output_file)

    def browse(self, tgl):
        p = {'value(D1)': 0}
        p['value(r1)'] = 1 # Mutasi harian
        p['value(startDt)'] = p['value(endDt)'] = str(tgl.day).zfill(2)
        p['value(startMt)'] = p['value(endMt)'] = tgl.month 
        p['value(startYr)'] = p['value(endYr)'] = tgl.year 
        return self.open_url('/accountstmt.do?value(actions)=acctstmtview', p)
    

if __name__ == '__main__':
    import sys
    from optparse import OptionParser
    from pprint import pprint
    from common import to_date
    pars = OptionParser()
    pars.add_option('-u', '--username')
    pars.add_option('-p', '--password')
    pars.add_option('-d', '--date', help='dd-mm-yyyy')
    pars.add_option('', '--mutasi-file')
    pars.add_option('', '--saldo-file')
    pars.add_option('', '--output-file')
    option, remain = pars.parse_args(sys.argv[1:])

    if option.mutasi_file:
        content = open_file(option.mutasi_file)
        parser = MutasiParser()
        parser.feed(content)
        pprint(parser.get_clean_data())
        sys.exit()

    if option.saldo_file:
        content = open_file(option.saldo_file)
        parser = SaldoParser()
        parser.feed(content)
        pprint(parser.get_clean_data())
        sys.exit()

    if not option.username or not option.password:
        print('--username dan --password harus diisi')
        sys.exit()

    if option.date:
        crawler = MutasiBrowser(option.username, option.password,
                                option.output_file)
        tgl = to_date(option.date)
        data = crawler.run(tgl)
        pprint(data)
    else:
        crawler = SaldoBrowser(option.username, option.password,
                               option.output_file)
        data = crawler.run()
        pprint(data)
