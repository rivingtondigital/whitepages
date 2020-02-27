import numpy as np
from PIL import Image
import pytesseract


class Band:
    __slots__ = ('first', 'last')

    def __init__(self, first, last):
        self.first = first
        self.last = last
    
    @property
    def width(self):
        return self.last - self.first
    
    def is_el(self, context_width):
        if self.width <= 1:
            return False
        if self.first == 0:
            return False
        if self.last == context_width-1:
            return False
        return True

    def __repr__(self):
        return "{}:{} => {}".format(self.first, self.last, self.width)


class MaskedSection:
    def __init__(self, parent, top, bottom, orientation=None, bits=None, id="0"):
        self.parent = parent
        self.top = top
        self.bottom = bottom
        self.id = id
        self._children = []
        
        if parent:
            self.bits = parent.bits[top:bottom]
            self.orientation = self.parent.orientation * -1
            self.rotate()
        else:
            self.orientation = 1
            self.bits = bits
        
        self._bands = []
        self.dirty = True
        
    def rotate(self):
        if self.orientation == -1:
            self.bits = self.rotate_fw(self.bits)
        else:
            self.bits = self.rotate_rv(self.bits)        
        self.bottom, _ = self.bits.shape

            
    @classmethod
    def PartitionMask(cls, im):
        bits = np.asarray(im, dtype='bool')
        return cls(parent=None, top=0, bottom=len(bits)-1, bits=bits)
        
    @property
    def children(self):
        if self.dirty or not self._children:
            self._children = []
            top = 0
            i = -1
            if not self.bands:
                # self._children.append(MaskedSection(self, top, self.bottom, id=self.id+'.'+str(0)))
                return self._children
            for i, b in enumerate(self.bands):
                self._children.append(MaskedSection(self, top, b.first+1, id=self.id+'.'+str(i)))
                top = b.last
            self._children.append(MaskedSection(self, b.last, self.bottom, id=self.id+'.'+str(i+1)))
            self.dirty = False
        return self._children
            
    @property
    def context(self):
        if self.parent is None:
            return self.bits
        return self.parent.context
    
    @property
    def bands(self):
        if not self._bands:
            self._bands = self.find_bands(self.bits)
            self._bands = self.filter_bands(self._bands)
            self._bands = sorted(self._bands, key=lambda x: x.first)
            if not self._bands:
                self.orientation *= -1
                self.rotate()
                self._bands = self.find_bands(self.bits)
                self._bands = self.filter_bands(self._bands)
                self._bands = sorted(self._bands, key=lambda x: x.first)              
        return self._bands
    
    # @property
    # def agg_bits(self):
    #     bits = np.array(self.bits, copy=True)
    #     for child in self.children:
    #         bits[child.top: child.bottom] &= child.agg_bits
    #     mask = self.mask
    #     bits &= mask
    #     if self.orientation == -1:
    #         bits = self.rotate_rv(bits)
    #     return bits
        
    @property
    def image(self):
        if self.orientation == -1:
            bits = self.rotate_rv(self.bits)
        else:
            bits = self.bits
        try:
            return Image.fromarray(bits.astype('uint8')*255)
        except Exception as e:
            return 'Failed to make image {}'.format(e)
    
    @property
    def text(self):
        try:
            return pytesseract.image_to_string(self.image)
        except Exception as e:
            return 'Failed to make text: {}'.format(e)
    
    def __repr__(self):
        return "{}:{}".format(self.id, len(self.children))

    @staticmethod
    def bander(bits):
        (rows, columns) = bits.shape
        blank_row = columns
        band = Band(first=0, last=0)
        for i in range(rows):
            if sum(bits[i]) < blank_row:
                if band.is_el(rows):
                    yield band
                band = Band(first=i, last=i)
            else:
                band.last = i
            
    # @property
    # def mask(self):
    #     base = np.ones(self.bits.shape)
    #     for band in self.bands:
    #         base[band.first:band.last] = 0
    #
    #     if self.orientation == -1:
    #         base = self.rotate_fw(base)
    #     else:
    #         base = self.rotate_rv(base)
    #
    #     return base
        
    @staticmethod
    def make_im(bits):
        return Image.fromarray(bits.astype('uint8')*255)
    
    @staticmethod
    def rotate_fw(bits):
        return np.rot90(bits, 3)
    
    @staticmethod
    def rotate_rv(bits):
        return np.rot90(bits, 1)
    
    @staticmethod
    def filter_bands(bands):
        return [x for x in bands if (bands[0].width * 1.0/ x.width) < 1.8]

    @staticmethod
    def find_bands(bits):
        bands = [x for x in MaskedSection.bander(bits)]
        ordered_bands = sorted(bands, key=lambda x: x.width, reverse=True)
        return ordered_bands


