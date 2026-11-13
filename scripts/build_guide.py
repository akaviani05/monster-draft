"""Render the shared HTML student guide to shaped Persian vector PDF.

Requires the OS's python3-gi, python3-cairo, Pango and Rsvg. This avoids browsers
and correctly shapes Persian/Latin runs, unlike unshaped PDF text drawing.
No dependency is added to the runner or website.
"""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import shutil
import sys
import cairo
import gi
gi.require_version('Pango','1.0')
gi.require_version('PangoCairo','1.0')
gi.require_version('Rsvg','2.0')
from gi.repository import Pango, PangoCairo, Rsvg

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output/pdf/student-guide-fa.pdf'
W,H=595.28,841.89
INK=(.188,.149,.247);MUTED=(.49,.46,.54);PURPLE=(.47,.38,.68)


class Node:
    def __init__(self,tag='',attrs=()):self.tag=tag;self.attrs=dict(attrs);self.children=[]
    def text(self):return ''.join(c.text() if isinstance(c,Node) else c for c in self.children)


class Parser(HTMLParser):
    def __init__(self):super().__init__();self.root=Node();self.stack=[self.root]
    def handle_starttag(self,tag,attrs):
        node=Node(tag,attrs);self.stack[-1].children.append(node)
        if tag not in ('meta','link','img','input','br'):self.stack.append(node)
        if tag=='br':self.stack[-1].children.append('\n')
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:self.stack=self.stack[:i];break
    def handle_data(self,data):self.stack[-1].children.append(data)


def find(node,tag):
    if node.tag==tag:yield node
    for child in node.children:
        if isinstance(child,Node):yield from find(child,tag)


class PDF:
    def __init__(self):
        OUT.parent.mkdir(parents=True,exist_ok=True)
        self.surface=cairo.PDFSurface(str(OUT),W,H);self.ctx=cairo.Context(self.surface)
        self.surface.set_metadata(cairo.PDF_METADATA_TITLE,'نبرد هیولاها | راهنمای دانش‌آموز')
        self.surface.set_metadata(cairo.PDF_METADATA_AUTHOR,'Monster Draft Duel')
        self.page=0;self.y=65;self.chapter='راهنمای دانش‌آموز'

    def rect(self,x,y,w,h,color,r=8):
        c=self.ctx;c.new_sub_path();c.arc(x+w-r,y+r,r,-1.57,0);c.arc(x+w-r,y+h-r,r,0,1.57);c.arc(x+r,y+h-r,r,1.57,3.14);c.arc(x+r,y+r,r,3.14,4.72);c.close_path();c.set_source_rgb(*color);c.fill()

    def layout(self,text,size=11,width=499,bold=False,ltr=False,color=INK,spacing=3):
        layout=PangoCairo.create_layout(self.ctx);PangoCairo.context_set_resolution(layout.get_context(),72)
        layout.set_width(int(width*Pango.SCALE));layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        font=Pango.FontDescription(('DejaVu Sans Mono' if ltr else 'Vazirmatn')+(' Bold' if bold else '')+f' {size}')
        layout.set_font_description(font);layout.set_spacing(int(spacing*Pango.SCALE))
        layout.get_context().set_base_dir(Pango.Direction.LTR if ltr else Pango.Direction.RTL)
        layout.set_auto_dir(False);layout.set_alignment(Pango.Alignment.LEFT if ltr else Pango.Alignment.RIGHT)
        layout.set_text(text,-1);return layout

    def draw(self,text,x,y,size=11,width=499,bold=False,ltr=False,color=INK,spacing=3):
        l=self.layout(text,size,width,bold,ltr,color,spacing);self.ctx.set_source_rgb(*color);self.ctx.move_to(x,y);PangoCairo.show_layout(self.ctx,l)
        return l.get_pixel_size()[1]

    def svg(self,name,x,y,w,h):
        handle=Rsvg.Handle.new_from_file(str(ROOT/'web/assets'/name))
        viewport=Rsvg.Rectangle();viewport.x=0;viewport.y=0;viewport.width=w;viewport.height=h
        self.ctx.save();self.ctx.translate(x,y);handle.render_document(self.ctx,viewport);self.ctx.restore()

    def new_page(self,chapter=None):
        if self.page:self.footer();self.surface.show_page()
        self.page+=1;self.y=73
        if chapter:self.chapter=chapter
        self.ctx.set_source_rgb(1,1,1);self.ctx.paint()
        self.draw('نبرد هیولاها',W-190,24,size=10,width=140,bold=True)
        self.draw(self.chapter,48,26,size=8,width=250,color=MUTED)
        self.ctx.set_source_rgb(.92,.90,.95);self.ctx.set_line_width(.7);self.ctx.move_to(48,53);self.ctx.line_to(W-48,53);self.ctx.stroke()

    def footer(self):
        self.ctx.set_source_rgb(.92,.90,.95);self.ctx.move_to(48,H-46);self.ctx.line_to(W-48,H-46);self.ctx.stroke()
        self.draw('قوانین نسخهٔ ۱ · کد بنویس، فکر کن، رقابت کن',155,H-36,size=7,width=390,color=MUTED)
        self.draw(str(self.page).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹')),48,H-37,size=9,width=30,color=PURPLE)

    def ensure(self,height):
        if self.y+height>H-67:self.new_page()

    def para(self,text,size=10.5,bold=False,kind='p'):
        text=text.strip()
        if not text:return
        l=self.layout(text,size,499,bold)
        h=l.get_pixel_size()[1]
        self.ensure(h+8);self.draw(text,48,self.y,size,499,bold,color=PURPLE if kind=='h' else INK);self.y+=h+8

    def code(self,text,size=8.5):
        l=self.layout(text.rstrip(),size,471,ltr=True,spacing=1);h=l.get_pixel_size()[1]+20
        self.ensure(h+10);self.rect(48,self.y,499,h,INK)
        self.draw(text.rstrip(),62,self.y+10,size=size,width=471,ltr=True,color=(.91,.87,.96),spacing=1);self.y+=h+10

    def notice(self,text):
        h=self.layout(text,10,471).get_pixel_size()[1]+24
        self.ensure(h+10);self.rect(48,self.y,499,h,(.95,.93,.98));self.draw(text,62,self.y+12,size=10,width=471,color=(.45,.37,.55));self.y+=h+10

    def table(self,node):
        rows=list(find(node,'tr'));widths=[98,108,293] if len(list(find(rows[0],'th')))==3 else [310,189]
        self.ensure(70)
        for i,row in enumerate(rows):
            cells=[n for n in row.children if isinstance(n,Node) and n.tag in ('td','th')]
            if not cells:continue
            # First source column occupies the rightmost area.
            widths=(([319,90,90] if rows[0].text().strip().startswith('بخش') else [140,270,89]) if len(cells)==3 else [150,349])
            heights=[self.layout(c.text().strip(),9,w-18,bold=i==0).get_pixel_size()[1] for c,w in zip(cells,widths)]
            h=max(heights)+14;self.ensure(h+8)
            self.rect(48,self.y,499,h,(.95,.93,.98) if i==0 else ((.985,.981,.992) if i%2 else (1,1,1)),r=0)
            x=W-48
            for c,w in zip(cells,widths):
                x-=w;self.draw(c.text().strip(),x+9,self.y+7,size=9,width=w-18,bold=i==0)
            self.y+=h
        self.y+=10

    def finish(self):self.footer();self.surface.finish()


def main():
    parser=Parser();parser.feed((ROOT/'web/guide.html').read_text())
    pdf=PDF();pdf.new_page('دفترچهٔ راهنمای دانش‌آموز')
    pdf.rect(35,78,525,660,(.97,.958,.985),18)
    pdf.draw('راهنمای شروع · ویژهٔ پایهٔ نهم',80,107,11,435,color=PURPLE)
    pdf.draw('هیولاهای کوچک،\nتصمیم‌های بزرگ!',65,154,32,465,bold=True)
    pdf.svg('monster-c.svg',75,302,142,135);pdf.svg('monster-b.svg',375,302,142,135);pdf.svg('monster-a.svg',208,272,178,170)
    pdf.draw('یک بازار، شش کارت و هزار راه برای بردن.',70,464,15,455,bold=True)
    pdf.draw('با پایتون یا C++ ربات خود را بسازید.\nعملکرد آن را بررسی کنید و ایده‌های تازه را بیازمایید.',75,511,12,445)
    for x,n,t in [(60,'۵۰','کارت در دسته'),(225,'۶','جای ثابت بازار'),(390,'۱۵','انتخاب برای هر ربات')]:
        pdf.rect(x,610,145,83,(.92,.895,.96));pdf.draw(n,x+10,619,25,125,bold=True,color=PURPLE);pdf.draw(t,x+10,663,9,125)
    for section in find(parser.root,'section'):
        title=next(find(section,'h2')).text()
        pdf.new_page(title)
        nodes=[child for child in section.children if isinstance(child,Node)]
        for index,child in enumerate(nodes):
            tag=child.tag
            if tag=='h2':pdf.para(child.text(),21,True,'h')
            elif tag=='h3':
                next_node=nodes[index+1] if index+1<len(nodes) else None
                next_height=pdf.layout(next_node.text().strip(),10.5).get_pixel_size()[1] if next_node and next_node.tag=='p' else (pdf.layout(next_node.text().rstrip(),8.5,471,ltr=True,spacing=1).get_pixel_size()[1]+30 if next_node and next_node.tag=='pre' else 60)
                pdf.ensure(48+next_height);pdf.para(child.text(),12.5,True)
            elif tag=='p':pdf.para(child.text())
            elif tag=='pre':pdf.code(child.text(),size=9.5 if section.attrs.get('id') in ('first-bot','cpp-bot') else 8.5)
            elif tag in ('ol','ul'):
                for i,item in enumerate(find(child,'li')):pdf.para(('• ' if tag=='ul' else str(i+int(child.attrs.get('start','1'))).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))+'. ')+item.text(),10)
            elif tag=='div':
                klass=child.attrs.get('class','')
                if 'notice' in klass:pdf.notice(child.text())
                elif 'table-wrap' in klass:pdf.table(next(find(child,'table')))
                elif 'sequence' in klass:pdf.code('P0  P1  P1  P0  P0  P1  P1  P0')
                elif 'eyebrow' in klass:pdf.para(child.text(),9,False,'h')
            elif tag=='span' and child.attrs.get('class')=='code-caption':pdf.para(child.text(),8)
    pdf.finish();(ROOT/'web/downloads').mkdir(exist_ok=True);shutil.copy2(OUT,ROOT/'web/downloads/student-guide-fa.pdf')
    print(f'{OUT} ({pdf.page} pages)')


if __name__=='__main__':main()
