"""Собирает docs/PRIMERKA_description.docx — полное описание проекта (только стандартная библиотека Python).

Запуск: python3 tools/make_doc.py
"""
import json
import os
import zipfile
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'docs', 'PRIMERKA_description.docx')
PRESETS = json.load(open(os.path.join(ROOT, 'models', 'presets.json'), encoding='utf8'))

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ' \
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ' \
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" ' \
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ' \
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'

body = []
images = []          # (rId, имя файла в архиве, путь)
TEXT_W = 9638        # ширина текста A4 при полях 2 см, DXA


def runs(text, bold=False, mono=False, size=None, color=None):
    """Текст с разметкой **жирный** и `код`."""
    out, i = [], 0
    parts = []
    while i < len(text):
        if text.startswith('**', i):
            j = text.index('**', i + 2); parts.append((text[i + 2:j], True, False)); i = j + 2
        elif text[i] == '`':
            j = text.index('`', i + 1); parts.append((text[i + 1:j], False, True)); i = j + 1
        else:
            j = min([k for k in (text.find('**', i), text.find('`', i)) if k != -1] or [len(text)])
            parts.append((text[i:j], False, False)); i = j
    for t, b, m in parts:
        if not t:
            continue
        rpr = ''
        if m or mono:
            rpr += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/><w:color w:val="1F4E46"/>'
        if b or bold:
            rpr += '<w:b/>'
        if color:
            rpr += '<w:color w:val="%s"/>' % color
        if size:
            rpr += '<w:sz w:val="%d"/>' % size
        out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % ('<w:rPr>%s</w:rPr>' % rpr if rpr else '', escape(t)))
    return ''.join(out)


def p(text='', style=None, align=None, keep=False):
    ppr = ''
    if style:
        ppr += '<w:pStyle w:val="%s"/>' % style
    if keep:
        ppr += '<w:keepNext/>'
    if align:
        ppr += '<w:jc w:val="%s"/>' % align
    body.append('<w:p>%s%s</w:p>' % ('<w:pPr>%s</w:pPr>' % ppr if ppr else '', runs(text)))


def h1(t):
    p(t, 'Heading1')


def h2(t):
    p(t, 'Heading2')


def bullets(items, numbered=False):
    for t in items:
        body.append('<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="%d"/></w:numPr></w:pPr>%s</w:p>'
                    % (2 if numbered else 1, runs(t)))


def code(lines):
    for ln in lines:
        body.append('<w:p><w:pPr><w:pStyle w:val="Code"/></w:pPr>%s</w:p>' % runs(ln, mono=True) if ln else
                    '<w:p><w:pPr><w:pStyle w:val="Code"/></w:pPr></w:p>')


def table(header, rows, widths):
    total = sum(widths)
    widths = [round(w * TEXT_W / total) for w in widths]
    widths[-1] += TEXT_W - sum(widths)
    def cell(text, w, head):
        shd = '<w:shd w:val="clear" w:color="auto" w:fill="E3EEEA"/>' if head else ''
        return ('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s</w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr>%s</w:p></w:tc>'
                % (w, shd, runs(text, bold=head, size=19)))
    x = ['<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/><w:tblBorders>' % TEXT_W]
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        x.append('<w:%s w:val="single" w:sz="4" w:space="0" w:color="BFC8C4"/>' % side)
    x.append('</w:tblBorders><w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="90" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>')
    x += ['<w:gridCol w:w="%d"/>' % w for w in widths]
    x.append('</w:tblGrid>')
    x.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>%s</w:tr>' % ''.join(cell(h, w, True) for h, w in zip(header, widths)))
    for r in rows:
        x.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>%s</w:tr>' % ''.join(cell(str(c), w, False) for c, w in zip(r, widths)))
    x.append('</w:tbl>')
    body.append(''.join(x))
    p('')


def image(path, caption, width_cm=11.0, px=(800, 867)):
    rid = 'rIdImg%d' % (len(images) + 1)
    name = 'image%d.jpg' % (len(images) + 1)
    images.append((rid, name, path))
    cx = int(width_cm * 360000); cy = int(cx * px[1] / px[0]); n = len(images)
    body.append(
        '<w:p><w:pPr><w:jc w:val="center"/><w:keepNext/></w:pPr><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        '<wp:extent cx="%d" cy="%d"/><wp:docPr id="%d" name="Picture %d"/>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
        '<pic:nvPicPr><pic:cNvPr id="%d" name="%s"/><pic:cNvPicPr/></pic:nvPicPr>'
        '<pic:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
        % (cx, cy, n, n, n, name, rid, cx, cy))
    p(caption, 'Caption', 'center')


# ======================= СОДЕРЖАНИЕ =======================
B = PRESETS['bodies']

p('PRIMERKA', 'Title')
p('Виртуальная примерка одежды на готовых 3D-заготовках', 'Subtitle')
p('Техническое описание прототипа: что использовано, как устроено и как запустить. Версия от 25.10.2026.')

h1('1. Задача и сценарий')
p('Покупатель вводит свои замеры, программа выбирает ближайшую из трёх готовых 3D-фигур, покупатель выбирает '
  'одежду из каталога магазина и видит, как она сидит, вместе с рекомендацией размера.')
bullets(['**Параметры.** Рост, обхват груди, талии и бёдер.',
         '**Модель.** Программа выбирает одну из трёх заготовок фигуры (худощавая, средняя, плотная) и масштабирует её под рост.',
         '**Каталог.** Покупатель выбирает футболку и/или джинсы. Артикулы отличаются только цветом или принтом.',
         '**Посадка.** Модель показывает вещь в выбранном размере (S–XL); рядом — рекомендация «ваш размер» и оценка по зонам: тесно / в самый раз / свободно.'],
        numbered=True)
p('Принципы, заданные заказчиком:')
bullets(['не использовать прошлые модели человека и одежды (man.fbx, присланные футболку и брюки);',
         'для показа 3D использовать model-viewer (modelviewer.dev);',
         'не более трёх заготовок фигуры;',
         'заготовки под каждый размер одежды на каждую фигуру, одна модель вещи используется многократно — меняется только цвет (принт).'])
image(os.path.join(ROOT, 'docs', 'screen-model.jpg'), 'Рисунок 1. Подобранная фигура «Средняя» в футболке с принтом и джинсах')

h1('2. Что использовано')
table(['Компонент', 'Что это', 'Зачем в проекте', 'Лицензия'], [
    ['model-viewer 3.5.0', 'Веб-компонент Google для показа GLB-моделей', 'Просмотр и вращение модели, перекраска материалов через Materials API', 'Apache-2.0'],
    ['MakeHuman: base.obj (hm08)', 'Базовая сетка человека, 19 158 вершин', 'Основа трёх фигур', 'CC0'],
    ['MakeHuman: macrodetails targets', 'Морфы «вес», «мышцы», «пол/возраст/тип»', 'Получение худощавой, средней и плотной фигуры', 'CC0'],
    ['MakeHuman: male_casualsuit04', 'Комплект «футболка + джинсы» с привязкой к телу (.mhclo) и текстурой', 'Модель одежды, которая садится на любую фигуру MakeHuman', 'CC0'],
    ['MakeHuman: eyes low-poly', 'Глаза', 'Чтобы у фигуры не было пустых глазниц', 'CC0'],
    ['Python 3 (стандартная библиотека)', 'Скрипт сборки', 'Морфы, посадка одежды, размеры, запись GLB и PNG', '—'],
    ['HTML / CSS / JavaScript', 'Интерфейс', 'Ввод замеров, выбор фигуры, каталог, подбор размера', '—'],
], [2.2, 3.0, 3.6, 1.2])
p('Почему так:')
bullets(['**model-viewer не создаёт модели** — он только показывает готовые GLB. Поэтому модели собираются скриптом заранее, а model-viewer их показывает.',
         '**MakeHuman** выбран потому, что его ассеты официально выпущены под CC0 (можно использовать коммерчески, без указания авторов), '
         'а одежда MakeHuman описана относительно тела и автоматически садится на любую фигуру, полученную морфами.',
         '**Без внешних библиотек** (numpy, Blender, Node.js): проект собирается на любом компьютере, где есть Python 3.'])

h1('3. Структура проекта')
table(['Путь', 'Назначение'], [
    ['index.html', 'Приложение: 4 шага, каталог, подбор размера, управление model-viewer'],
    ['models/body_slim.glb, body_avg.glb, body_heavy.glb', 'Заготовки: фигура + глаза + футболка и джинсы во всех размерах S–XL'],
    ['models/textures/print.png', 'Исходная ткань комплекта: футболка с принтом и джинсы индиго'],
    ['models/textures/fabric.png', 'Фактура денима в оттенках серого — цвет задаёт материал'],
    ['models/presets.json', 'Замеры фигур, таблица размеров, запас по зонам'],
    ['models/bundle.js', 'Всё перечисленное одним файлом (data-URI), чтобы сайт открывался без сервера'],
    ['vendor/model-viewer.js', 'model-viewer, встроенный в проект как обычный скрипт'],
    ['tools/build_presets.py', 'Сборка заготовок из ассетов MakeHuman'],
    ['tools/mhlib.py', 'Чтение OBJ, .target, .mhclo; посадка одежды; срезы и обхваты'],
    ['tools/pngio.py', 'Чтение и запись PNG без внешних библиотек'],
    ['tools/make_doc.py', 'Генерация этого документа'],
    ['source/makehuman/', 'Исходные CC0-ассеты MakeHuman (для пересборки)'],
    ['docs/', 'Этот документ и скриншоты'],
], [4.2, 5.8])

h1('4. Как собираются заготовки (tools/build_presets.py)')
h2('4.1. Фигуры из морфов MakeHuman')
p('Берётся базовая сетка `base.obj`. На неё накладываются морфы (targets) — списки смещений вершин. '
  'Мужская фигура 25 лет — это сумма трёх морфов `*-male-young` (африканский, азиатский, европеоидный тип) по 1/3. '
  'Затем добавляются морфы веса и мышц с подобранными коэффициентами:')
rows = []
for k, b in B.items():
    m = b['measurements']
    rows.append([b['name'], ', '.join('%s × %.2f' % (n, v) for n, v in b['morphs']), m['height'], m['chest'], m['waist'], m['hips']])
table(['Фигура', 'Морфы (universal-male-young-…)', 'Рост', 'Грудь', 'Талия', 'Бёдра'], rows, [1.5, 4.5, 0.9, 0.9, 0.9, 0.9])
p('Все размеры в сантиметрах. Рост у всех заготовок одинаковый (173 см): под рост покупателя модель масштабируется в браузере.')

h2('4.2. Как измеряются обхваты')
bullets(['Тело режется горизонтальной плоскостью; находятся точки пересечения рёбер треугольников с плоскостью.',
         'Точки делятся на группы по зазорам вдоль оси X (торс, руки, ноги); берётся группа, содержащая центр (торс).',
         'Обхват = периметр выпуклой оболочки среза — так ложится сантиметровая лента.',
         'Грудь — максимум в зоне 68–73 % роста, талия — минимум в зоне 58–66 %, бёдра — максимум в зоне 47–54 %.',
         'Вершины рук заранее помечены по средней фигуре, чтобы обхват груди не захватывал руки у плотной фигуры.'])

h2('4.3. Посадка одежды на фигуру (.mhclo)')
p('Каждая вершина вещи в MakeHuman привязана к трём вершинам тела с весами и смещением. После морфов вершина вещи пересчитывается так:')
code(['v = w0·B[i0] + w1·B[i1] + w2·B[i2] + (dx·sx, dy·sy, dz·sz)'])
p('где B — вершины тела после морфов, а sx, sy, sz — масштаб фигуры по осям (расстояние между двумя опорными вершинами тела, '
  'делённое на эталонное из файла). Поэтому одна и та же модель одежды садится на все три фигуры.')
p('Комплект `male_casualsuit04` — одна сетка; она делится на футболку и джинсы по связности (это два отдельных куска).')

h2('4.4. Размеры S–XL')
p('Таблица размеров изделий (обхваты готовой вещи, см):')
gt, gj = PRESETS['garments']['tee']['sizes'], PRESETS['garments']['jeans']['sizes']
table(['Размер', 'Футболка: грудь', 'Джинсы: талия', 'Джинсы: бёдра'],
      [[s, gt[s]['chest'], gj[s]['waist'], gj[s]['hips']] for s in PRESETS['sizes']], [1, 2, 2, 2])
p('Вещь, посаженная MakeHuman, имеет свой обхват. Чтобы получить нужный размер, каждая вершина сдвигается по нормали на')
code(['d = (обхват размера − обхват посадки) / 2π + 0,35 см'])
bullets(['**Футболка:** ниже груди сдвиг одинаков — ткань висит прямо; к горловине сдвиг плавно уменьшается до 25 %; рукава — 50 %.',
         '**Джинсы:** сверху — по талии, у бёдер — по бёдрам, штанина к низу сужается до 35 % от сдвига бёдер.',
         '**Пояс джинсов** сидит ниже природной талии, поэтому запас размера переносится на уровень пояса: обхват пояса = тело на поясе + (обхват размера − талия).',
         '**Тесный размер** облегает тело, но не уходит под кожу (сдвиг не меньше −0,2 см). «Тесно» видно в оценке зон.',
         '**Свободный размер** ограничен 9 см сдвига, чтобы вещь не превращалась в шар.',
         '**Футболка поверх джинсов:** футболка не меняется, а джинсы выше подола прижимаются так, чтобы не выходить за самый узкий размер футболки; переход плавный (2 см).'])
p('Итого: 3 фигуры × 2 вещи × 4 размера = **24 заготовки**.')

h2('4.5. Что лежит в GLB')
p('На каждую фигуру — один файл GLB (около 0,8 МБ). Внутри 10 сеток, у каждой свой материал:')
table(['Сетка / материал', 'Описание'], [
    ['body / skin', 'Тело, однотонный материал кожи'],
    ['eyes / eyes', 'Глаза'],
    ['tee_S, tee_M, tee_L, tee_XL', 'Футболка в 4 размерах; alphaMode MASK, двусторонний материал'],
    ['jeans_S, jeans_M, jeans_L, jeans_XL', 'Джинсы в 4 размерах; alphaMode MASK, двусторонний материал'],
], [4, 6])
p('Почему все размеры в одном файле: model-viewer показывает только одну модель, поэтому тело и вещи нельзя загрузить отдельными файлами и совместить. '
  'Ненужные размеры скрываются прозрачностью материала: при alphaMode MASK пиксели с альфой 0 отбрасываются целиком и не перекрывают другие вещи.')

h2('4.6. Текстуры и bundle.js')
bullets(['`print.png` — исходная текстура комплекта (2048 → 1024 px): футболка с принтом и джинсы индиго.',
         '`fabric.png` — та же текстура в оттенках серого, нормированная по яркости денима. Материал умножает её на цвет, поэтому один деним даёт чёрные, серые и песочные джинсы.',
         '`bundle.js` — три GLB и две текстуры в виде data-URI плюс presets.json. Страница берёт всё из этого файла и не делает ни одного сетевого запроса.'])

h1('5. Как работает приложение (index.html)')
h2('5.1. Выбор фигуры')
p('Модель масштабируется под рост покупателя: s = рост / 173. Выбирается заготовка с минимальным расстоянием:')
code(['D = √((грудь − s·грудьМ)² + (талия − s·талияМ)² + (бёдра − s·бёдраМ)²)'])
p('В браузере это атрибут `scale` у model-viewer. Рядом выводится таблица «Вы / Модель».')

h2('5.2. Рекомендация размера')
p('Для каждой зоны считается запас = обхват изделия − замер покупателя и сравнивается с порогами:')
table(['Вещь / зона', 'Тесно', 'В самый раз', 'Свободно'], [
    ['Футболка / грудь', 'меньше +2 см', 'от +2 до +14 см', 'больше +14 см'],
    ['Джинсы / талия', 'меньше −1 см', 'от −1 до +6 см', 'больше +6 см'],
    ['Джинсы / бёдра', 'меньше 0 см', 'от 0 до +10 см', 'больше +10 см'],
], [3, 2, 2.5, 2])
p('Рекомендуется размер с наименьшим штрафом: «тесно» — 300, «свободно» — 100, плюс отклонение от середины коридора. '
  'Рекомендация считается по замерам покупателя, а не по модели — так она точнее.')

h2('5.3. Каталог и перекраска')
table(['Артикул', 'Название', 'Как показан'], [
    ['TSH-WHT / BLK / NVY / OLV', 'Футболка белая, чёрная, синяя, олива', 'Одна сетка, цвет материала'],
    ['TSH-PRT', 'Футболка с принтом', 'Текстура print.png'],
    ['JNS-IND', 'Джинсы индиго', 'Текстура print.png'],
    ['JNS-BLK / GRY / SND', 'Джинсы чёрные, серые, песочные', 'Текстура fabric.png × цвет'],
], [3, 4, 3])
p('При выборе артикула и размера страница через Materials API model-viewer: (1) ставит альфу 1 у материала выбранного размера и 0 у остальных, '
  '(2) задаёт цвет `setBaseColorFactor`, (3) подставляет текстуру `setTexture`. Новая модель при этом не загружается — смена мгновенная.')
p('Профиль (замеры, выбранные вещи и размеры) сохраняется в localStorage браузера и восстанавливается при следующем открытии.')
image(os.path.join(ROOT, 'docs', 'screen-catalog.jpg'), 'Рисунок 2. Каталог магазина и шаг «Как сидит» с рекомендацией размера')

h1('6. Ключевые решения и от чего отказались')
table(['Проблема', 'Решение'], [
    ['model-viewer не умеет создавать модели', 'Модели собираются Python-скриптом из CC0-ассетов MakeHuman и показываются в model-viewer'],
    ['Старые модели нельзя использовать', 'Тело, одежда и глаза — новые, из MakeHuman'],
    ['Одна сцена model-viewer — одна модель', 'Все размеры в одной GLB на фигуру, переключение прозрачностью материала (MASK)'],
    ['Тесный размер выглядел как дыры (кожа проступала сквозь ткань)', 'Тесная вещь облегает тело; «тесно» показывается в оценке зон'],
    ['Низ футболки расширялся под самые широкие джинсы', 'Футболку не трогаем, прижимаем джинсы под ней'],
    ['Браузеры не грузят ES-модули со страниц из файла (file://)', 'model-viewer переделан в обычный скрипт (vendor/model-viewer.js), модели — в bundle.js'],
    ['Плотная фигура: руки прилегают к торсу и попадали в обхват груди', 'Вершины рук помечаются заранее по средней фигуре'],
], [4.5, 5.5])

h1('7. Запуск и загрузка на GitHub')
h2('7.1. Запуск у любого пользователя')
bullets(['Скачать проект с GitHub: **Code → Download ZIP** и распаковать, или `git clone`.',
         'Открыть `index.html` двойным кликом в Chrome, Edge, Firefox или Safari.'], numbered=True)
p('Не нужны ни интернет, ни сервер, ни установка программ: все модели, текстуры и model-viewer лежат в проекте.')
p('Можно открыть и через локальный сервер:')
code(['python3 -m http.server 8765', '# затем открыть http://localhost:8765'])
h2('7.2. Загрузка на GitHub')
p('Через сайт: создать пустой репозиторий на github.com → **Add file → Upload files** → перетащить содержимое папки проекта (без архива) → **Commit changes**.')
p('Через командную строку:')
code(['cd primerka',
      'git init',
      'git add .',
      'git commit -m "PRIMERKA: примерка на заготовках model-viewer"',
      'git branch -M main',
      'git remote add origin https://github.com/<логин>/primerka.git',
      'git push -u origin main'])
p('Размер проекта около 17 МБ, самый большой файл — models/bundle.js (5 МБ). Это в пределах ограничений GitHub (100 МБ на файл), Git LFS не нужен.')
p('Чтобы сайт открывался прямо по ссылке, можно включить GitHub Pages: Settings → Pages → Deploy from a branch → main / (root).')
h2('7.3. Пересборка заготовок')
code(['python3 tools/build_presets.py   # модели, текстуры, presets.json, bundle.js',
      'python3 tools/make_doc.py        # этот документ'])
p('Сборка занимает около 3 секунд и полностью воспроизводима: из одних и тех же исходников получаются байт-в-байт одинаковые файлы. '
  'Фигуры настраиваются в `BODIES`, таблица размеров — в `GARMENTS` в начале build_presets.py.')

h1('8. Ограничения и следующие шаги')
bullets(['Только мужские фигуры и одна поза (A-поза).',
         'Размеры S–XL: покупателю с талией больше 100 см не хватит XL.',
         'Ткань не симулируется: посадка — сдвиг по нормали, без складок.',
         'В каталоге два лекала (футболка и джинсы). Новое лекало — новый комплект одежды MakeHuman или своя модель с .mhclo.',
         'Пороги «тесно / свободно» условные — их нужно подобрать на пилоте с магазином.'])
p('Следующие шаги:')
bullets(['женские заготовки тем же конвейером (морфы female-young);',
         'размеры XS и XXL, больше лекал (худи, шорты, рубашки);',
         'кнопка «Посмотреть в AR» (model-viewer поддерживает AR на телефонах);',
         'встраиваемый виджет для сайтов магазинов и QR-код на бирке.'])

h1('9. Лицензии')
bullets(['Ассеты MakeHuman (тело, морфы, одежда, глаза) — CC0 1.0. Правообладатели на момент выпуска: Data Collection AB, Joel Palmius, Jonas Hauquier. Указывать авторов не обязательно.',
         'model-viewer — Google, Apache-2.0 (текст лицензии: vendor/LICENSE-model-viewer.txt).',
         'Код проекта (index.html, tools/) написан для PRIMERKA.'])


# ======================= СБОРКА DOCX =======================

def styles():
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles %s>'
            '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri" w:eastAsia="Calibri"/>'
            '<w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="ru-RU"/></w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
            '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:spacing w:after="60"/></w:pPr><w:rPr><w:b/><w:color w:val="2F5D50"/><w:sz w:val="56"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:color w:val="595959"/><w:sz w:val="30"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:keepNext/><w:spacing w:before="360" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>'
            '<w:rPr><w:b/><w:color w:val="2F5D50"/><w:sz w:val="32"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr>'
            '<w:rPr><w:b/><w:color w:val="1D1D1F"/><w:sz w:val="26"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/>'
            '<w:pPr><w:spacing w:after="60"/><w:ind w:left="720"/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/>'
            '<w:pPr><w:shd w:val="clear" w:color="auto" w:fill="F2F4F3"/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:ind w:left="284"/></w:pPr>'
            '<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/><w:sz w:val="19"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/>'
            '<w:pPr><w:spacing w:before="60" w:after="240"/></w:pPr><w:rPr><w:i/><w:color w:val="595959"/><w:sz w:val="19"/></w:rPr></w:style>'
            '</w:styles>') % W


def numbering():
    def absn(i, fmt, text):
        return ('<w:abstractNum w:abstractNumId="%d"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/>'
                '<w:numFmt w:val="%s"/><w:lvlText w:val="%s"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>%s</w:lvl></w:abstractNum>'
                % (i, fmt, text, '<w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr>' if fmt == 'bullet' else ''))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering %s>%s%s'
            '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num></w:numbering>'
            % (W, absn(0, 'bullet', ''), absn(1, 'decimal', '%1.')))


def build():
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document %s><w:body>%s'
           '<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="11906" w:h="16838"/>'
           '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr>'
           '</w:body></w:document>') % (W, ''.join(body))
    footer = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr %s><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
              '<w:r><w:rPr><w:color w:val="808080"/><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">PRIMERKA · стр. </w:t></w:r>'
              '<w:r><w:rPr><w:color w:val="808080"/><w:sz w:val="18"/></w:rPr><w:fldChar w:fldCharType="begin"/></w:r>'
              '<w:r><w:rPr><w:color w:val="808080"/><w:sz w:val="18"/></w:rPr><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
              '<w:r><w:rPr><w:color w:val="808080"/><w:sz w:val="18"/></w:rPr><w:fldChar w:fldCharType="separate"/></w:r>'
              '<w:r><w:rPr><w:color w:val="808080"/><w:sz w:val="18"/></w:rPr><w:t>1</w:t></w:r>'
              '<w:r><w:rPr><w:color w:val="808080"/><w:sz w:val="18"/></w:rPr><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>') % W
    rels = ['<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
            '<Relationship Id="rIdNum" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>',
            '<Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>']
    rels += ['<Relationship Id="%s" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/%s"/>' % (r, n)
             for r, n, _ in images]
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/><Default Extension="jpg" ContentType="image/jpeg"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
          '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
          '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
          '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
          '</Types>')
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>PRIMERKA — описание прототипа</dc:title><dc:language>ru-RU</dc:language>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">2026-10-25T12:00:00Z</dcterms:created></cp:coreProperties>')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ct)
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                   '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                   '</Relationships>')
        z.writestr('docProps/core.xml', core)
        z.writestr('word/document.xml', doc)
        z.writestr('word/styles.xml', styles())
        z.writestr('word/numbering.xml', numbering())
        z.writestr('word/footer1.xml', footer)
        z.writestr('word/_rels/document.xml.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>' % ''.join(rels))
        for _, n, path in images:
            z.write(path, 'word/media/' + n)
    print('Готово:', OUT)


if __name__ == '__main__':
    build()
