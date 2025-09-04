import hashlib
import struct

class OTP:
    MD4 = 4
    MD5 = 5

    def __init__(self, seq=0, seed="", passphrase=""):
        self.seq = seq
        self.seed = seed
        self.passphrase = passphrase
        self.hash = None

    def otp1(self, n, s, p):
        self.seq = n
        self.seed = s
        self.passphrase = p

    def calcmd5(self):
        self._md5calc()

    def calcsha1(self):
        self._sha1calc()

    @staticmethod
    def _otpfoldregs(regs):
        """Fold 16-byte result to 8 bytes"""
        ac = regs[0] ^ regs[2]
        bd = regs[1] ^ regs[3]
        fold = []
        for _ in range(4):
            fold.append(ac & 0xff)
            ac >>= 8
        for _ in range(4):
            fold.append(bd & 0xff)
            bd >>= 8
        return fold

    def _md5calc(self):
        """MD5-based OTP calculation"""
        md5 = hashlib.md5()
        md5.update((self.seed + self.passphrase).encode("ascii"))
        digest = md5.digest()[::-1]   # reverse
        regs = self._digest_to_regs(digest)

        tmpseq = self.seq
        while tmpseq + 1 > 0:
            self.hash = self._otpfoldregs(regs)
            dest = bytes(self.hash)
            md5 = hashlib.md5()
            md5.update(dest)
            digest = md5.digest()[::-1]
            regs = self._digest_to_regs(digest)
            tmpseq -= 1

    def _sha1calc(self):
        """SHA1-based OTP calculation"""
        sha1 = hashlib.sha1()
        sha1.update((self.seed + self.passphrase).encode("ascii"))
        digest = sha1.digest()[::-1]
        regs = self._digest_to_regs(digest)

        tmpseq = self.seq
        while tmpseq + 1 > 0:
            self.hash = self._otpfoldregs(regs)
            dest = bytes(self.hash)
            sha1 = hashlib.sha1()
            sha1.update(dest)
            digest = sha1.digest()[::-1]
            regs = self._digest_to_regs(digest)
            tmpseq -= 1

    @staticmethod
    def _digest_to_regs(digest):
        """Convert reversed digest into 4 regs (int32)."""
        # 16 bytes → 4x 4-byte hex strings
        hexstrs = [digest[i:i+4].hex().upper() for i in range(0, 16, 4)]
        AA, BB, CC, DD = hexstrs[3], hexstrs[2], hexstrs[1], hexstrs[0]
        return [
            int(AA, 16),
            int(BB, 16),
            int(CC, 16),
            int(DD, 16),
        ]

    def tolong(self):
        wi = 0
        for b in self.hash:
            wi = (wi << 8) | (b & 0xff)
        return wi

    def __str__(self):
        wi = self.tolong()
        tmplong = wi
        parity = 0
        for _ in range(0, 64, 2):
            parity += tmplong & 0x3
            tmplong >>= 2

        tmpstr = ""
        for i in range(4, -1, -1):
            tmpstr += OTP.btoe(((wi >> (i * 11 + 9)) & 0x7ff)) + " "
        tmpstr += OTP.btoe(((wi << 2) & 0x7fc) | (parity & 0x03))
        return tmpstr

    @staticmethod
    def btoe(index):
        if 0 <= index < len(OTP.words):
            return OTP.words[index]
        return "bogus"


    words = [
        "A", "ABE", "ACE", "ACT", "AD", "ADA", "ADD", "AGO", "AID", "AIM",

    ]
