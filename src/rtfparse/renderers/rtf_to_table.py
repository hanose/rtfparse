from collections import deque
from rtfparse import entities
from rtfparse.renderers import Renderer
import bs4

class RTFTableToHTML(Renderer):
    def __init__(self, ) -> None:
        super().__init__()

        # only groups with these names will be looked into
        self.important_groups = ["unknown", "trowd", "intbl", "animtext", "line", "cell", "row", "field", "fldinst", "line"]

        self.rendered = ''

        # queues where style options will be stored
        self.cell_width_queue = deque()
        self.cell_coordinates = deque()
        self.left_indent = deque()
        self.text_align = ''
        self.border_width = []
        self.borders = {'top': deque(), 'right': deque(), 'bottom': deque(), 'left': deque()}

        # store options for cell in cell_start
        self.cell_start = ''
        self.inside_cell = False
        self.cell_start_written = False

    def table_controls(self, cw: entities.Control_Word) -> str:

        table_control_words = {"trowd": '\n' + ' ' * 4 + "<table><tr>", "row": "</tr></table>",
                               "tab": "&nbsp;&nbsp;&nbsp;&nbsp;",
                               "line": "<br>", "par": "<br>"}

        if cw.control_name in table_control_words:
            return table_control_words.get(cw.control_name)
        elif cw.control_name == 'pard':
            self.text_align = ''
            return ""
        elif cw.control_name == "cellx":
            return self.cell_width(cw)
        elif cw.control_name == "li":
            return self.cell_left_indent(cw)
        elif cw.control_name in ['ql', 'qr', 'qc']:
            return self.cell_text_align(cw)
        elif cw.control_name in ['clbrdrb', 'clbrdrt', 'clbrdrl', 'clbrdrr']:
            return self.cell_borders(cw)
        elif cw.control_name == "cell":
            return self.table_cell_end(cw)
        else:
            return ""

    def table_cell_start(self, cw: entities.Control_Word) -> str:
        width_opt = ''
        li_opt = ''
        align_opt = ''
        border_width_opt = "border-width: " + \
                           'px '.join([str(x.popleft()) if len(x) > 0 else '0' for x in self.borders.values()]) + 'px;'

        if len(self.cell_width_queue) > 0:
            _width = abs(round(self.cell_width_queue.popleft(), 3))
            width_opt = f"min-width: {_width}in; max-width: {_width}in; "
            self.cell_coordinates.popleft()
        if len(self.left_indent) > 0:
            li_opt = self.left_indent.popleft()
        if self.text_align:
            align_opt = self.text_align

        self.cell_start = '\n' + ' ' * 8 + '<td style="' + width_opt + li_opt + align_opt + border_width_opt + '"><pre>'

        return ''

    def cell_width(self, cw: entities.Control_Word) -> str:
        # get cell width in points (pt). Original units are assumed to be twips
        offset = 0

        if len(self.cell_width_queue) > 0:
            offset = self.cell_coordinates[-1]

        cell_width = (cw.parameter - offset) / 1440
        self.cell_coordinates.append(cw.parameter)
        self.cell_width_queue.append(abs(round(cell_width, 3)))

        return ""

    def cell_text_align(self, cw: entities.Control_Word) -> str:
        translated = {'ql': 'left', 'qr': 'right', 'qc': 'center'}
        self.text_align = f'text-align: {translated.get(cw.control_name)}; '
        return ""

    def cell_borders(self, cw: entities.Control_Word) -> str:
        translated = {'clbrdrt': 'top', 'clbrdrb': 'bottom', 'clbrdrl': 'left', 'clbrdrr': 'right'}
        self.borders[translated[cw.control_name]].append(1)
        return ""

    def cell_left_indent(self, cw: entities.Control_Word) -> str:
        self.left_indent.append(f"text-indent: {abs(round(cw.parameter / 1440, 3))}in; ")
        return ""

    def table_cell_end(self, cw: entities.Control_Word) -> str:
        self.inside_cell = False
        _width = ''

        if not self.cell_start_written:
            border_width_opt = "border-width: " + \
                               'px '.join(
                                   [str(x.popleft()) if len(x) > 0 else '0' for x in self.borders.values()]) + 'px;'

            if len(self.cell_width_queue) > 0:
                cell_width = abs(round(self.cell_width_queue.popleft(), 3))
                self.cell_coordinates.popleft()
                _width = f' style="min-width: {cell_width}in; max-width: {cell_width}in; {border_width_opt}" '
            return '\n' + ' ' * 8 + '<td' + _width + '><pre>' + '</pre></td>'
        else:
            self.cell_start_written = False
            return '</pre></td>'

    @staticmethod
    def render_symbol(item: entities.Control_Symbol) -> None:
        # Obsolete formula character used by Word 5.1 for Macintosh
        symbols_table = {"|": '', "~": "\u00a0", '-': '', "_": "\u2011", ":": '', }

        if item.text in symbols_table:
            return symbols_table.get(item.text)
        elif item.text == "*":
            logger.warning("Found an IGNORABLE control symbol which is not a group start!")
        # Probably any symbol converted from a hex code: \'hh
        else:
            return item.text

    def render(self, parsed: entities.Group, in_group='') -> str:

        for item in parsed.structure:
            if in_group and ((hasattr(item, 'name') and item.name == in_group) or in_group in item.parents) or not in_group:
                if isinstance(item, entities.Group):
                    if item.name in self.important_groups + [in_group]:
                        self.render(item, in_group=in_group)
                elif isinstance(item, entities.Control_Word):
                    self.rendered += self.table_controls(item)
                elif isinstance(item, entities.Control_Symbol):
                    self.rendered += self.render_symbol(item)
                elif isinstance(item, entities.Plain_Text):

                    if not self.inside_cell:
                        self.table_cell_start(item)  # creates self.cell_start string
                        self.rendered += self.cell_start
                        self.inside_cell = True
                        self.cell_start_written = True

                    self.rendered += item.text

                else:
                    pass

        return self.rendered

class RTFToHTMLSoup(Renderer):
    
    def __init__(self, ) -> None:
        super().__init__()

        # only groups with these names will be looked into
        self.important_groups = ["unknown", "trowd", "intbl", "animtext", "line", "cell", "row", "field", "fldinst", "line"]

        self.rendered = bs4.BeautifulSoup()

        self.table = self.rendered.new_tag('table', style='')
        self.row = self.rendered.new_tag('tr', style='')
        self.current_cell = self.rendered.new_tag('td', style='')
        self.current_cell.append(self.rendered.new_tag('pre'))

        # queues where style options will be stored
        self.cell_width_queue = deque()
        self.cell_coordinates = deque()
        self.left_indent = deque()
        self.text_align = ''
        self.border_width = []
        self.borders = {'top': deque(), 'right': deque(), 'bottom': deque(), 'left': deque()}

        # store options for cell in cell_start
        self.cell_start = ''
        self.inside_cell = False
        self.cell_start_written = False

    def table_controls(self, cw: entities.Control_Word) -> None:

        table_control_words = {"tab": "&nbsp;&nbsp;&nbsp;&nbsp;", "line": self.rendered.new_tag("br"),
                               "par": self.rendered.new_tag("br")}

        # beginning of rtf row-> append current table to the soup and begin collecting data in a new table tag
        if cw.control_name == "trowd" and self.table.contents:

            self.table.append(self.row)
            self.rendered.append(self.table)

            self.table = self.rendered.new_tag('table', style='')
            self.row = self.rendered.new_tag('tr', style='')
            self.current_cell = self.rendered.new_tag('td', style='')
            self.current_cell.append(self.rendered.new_tag('pre'))

        # end of rtf row -> append current table to the soup and begin collecting data in a new table tag
        elif cw.control_name == "row" and self.row.contents:
            self.table.append(self.row)
            self.rendered.append(self.table)

            self.table = self.rendered.new_tag('table', style='')
            self.row = self.rendered.new_tag('tr', style='')
            self.current_cell = self.rendered.new_tag('td', style='')
            self.current_cell.append(self.rendered.new_tag('pre'))

        elif cw.control_name in table_control_words:
            self.current_cell.pre.append(table_control_words.get(cw.control_name))
        elif cw.control_name == 'pard':
            pass
        elif cw.control_name == 'trhdr':
            self.mark_header(cw)
        elif cw.control_name == "cellx":
            self.cell_width(cw)
        elif cw.control_name == "li":
            self.cell_left_indent(cw)
        elif cw.control_name in ['ql', 'qr', 'qc']:
            self.cell_text_align(cw)
        elif cw.control_name in ['clbrdrb', 'clbrdrt', 'clbrdrl', 'clbrdrr']:
            self.cell_borders(cw)
        elif cw.control_name == "cell":
            self.table_cell_end(cw)
        else:
            pass

    def table_cell_start(self) -> None:
        width_opt = ''
        li_opt = ''
        align_opt = ''
        border_width_opt = "border-width: " + \
                           'px '.join([str(x.popleft()) if len(x) > 0 else '0' for x in self.borders.values()]) + 'px;'

        if len(self.cell_width_queue) > 0:
            _width = abs(round(self.cell_width_queue.popleft(), 3))
            width_opt = f"min-width: {_width}in; max-width: {_width}in; "
            self.cell_coordinates.popleft()
        if len(self.left_indent) > 0:
            li_opt = self.left_indent.popleft()
        if self.text_align:
            align_opt = self.text_align

        self.current_cell['style'] = width_opt + li_opt + align_opt + border_width_opt

    def cell_width(self, cw: entities.Control_Word) -> None:
        # get cell width in points (pt). Original units are assumed to be twips
        offset = 0

        if len(self.cell_width_queue) > 0:
            offset = self.cell_coordinates[-1]

        cell_width = (cw.parameter - offset) / 1440
        self.cell_coordinates.append(cw.parameter)
        self.cell_width_queue.append(abs(round(cell_width, 3)))

    def cell_text_align(self, cw: entities.Control_Word) -> None:
        translated = {'ql': 'left', 'qr': 'right', 'qc': 'center'}
        self.text_align = f'text-align: {translated.get(cw.control_name)}; '

    def cell_borders(self, cw: entities.Control_Word) -> None:
        translated = {'clbrdrt': 'top', 'clbrdrb': 'bottom', 'clbrdrl': 'left', 'clbrdrr': 'right'}
        self.borders[translated[cw.control_name]].append(1)

    def cell_left_indent(self, cw: entities.Control_Word) -> None:
        self.left_indent.append(f"text-indent: {abs(round(cw.parameter / 1440, 3))}in; ")

    def table_cell_end(self, cw: entities.Control_Word) -> None:
        self.inside_cell = False
        _width = ''

        if not self.cell_start_written:
            border_width_opt = "border-width: " + \
                               'px '.join(
                                   [str(x.popleft()) if len(x) > 0 else '0' for x in self.borders.values()]) + 'px;'

            if len(self.cell_width_queue) > 0:
                cell_width = abs(round(self.cell_width_queue.popleft(), 3))
                self.cell_coordinates.popleft()
                _width = f'min-width: {cell_width}in; max-width: {cell_width}in; {border_width_opt}'

            self.current_cell['style'] += _width
        else:
            self.cell_start_written = False

        self.row.append(self.current_cell)
        self.current_cell = self.rendered.new_tag('td', style='')
        self.current_cell.append(self.rendered.new_tag('pre'))
        
    def mark_header(self, cw: entities.Control_Word) -> None:
        self.table['class'] = 'header_row'
                
    @staticmethod
    def render_symbol(item: entities.Control_Symbol) -> None:
        # Obsolete formula character used by Word 5.1 for Macintosh
        symbols_table = {"|": '', "~": "\u00a0", '-': '', "_": "\u2011", ":": '', }

        if item.text in symbols_table:
            return symbols_table.get(item.text)
        elif item.text == "*":
            logger.warning("Found an IGNORABLE control symbol which is not a group start!")
        # Probably any symbol converted from a hex code: \'hh
        else:
            return item.text

    def render(self, parsed: entities.Group, in_group='') -> bs4.BeautifulSoup:

        for item in parsed.structure:
            if in_group and ((hasattr(item, 'name') and item.name == in_group) or in_group in item.parents) or not in_group:
                if isinstance(item, entities.Group):
                    if item.name in self.important_groups + [in_group]:
                        self.render(item, in_group=in_group)
                elif isinstance(item, entities.Control_Word):
                    self.table_controls(item)
                elif isinstance(item, entities.Control_Symbol):
                    self.current_cell.pre.append(self.render_symbol(item))
                elif isinstance(item, entities.Plain_Text):

                    if not self.inside_cell:
                        self.table_cell_start()  # creates self.cell_start string
                        self.inside_cell = True
                        self.cell_start_written = True

                    self.current_cell.pre.append(item.text)

                else:
                    pass
        # smooth cells before returning - i.e. concatenate strings inside each cell so each cell would have only 1 string inside
        self.rendered.smooth()

        return self.rendered

