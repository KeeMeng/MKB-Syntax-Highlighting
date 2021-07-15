import sublime
import sublime_plugin
import re
import json
import os.path
import webbrowser
from copy import deepcopy

try:
	path = os.path.join(os.path.dirname(os.path.realpath(__file__)),"MKBdocs.json")
	with open(path, "r", encoding="utf-8") as jsondocs:
		mkbjson = json.load(jsondocs)
		print("MKBdocs loaded")

except:
	try:
		print("MKBdocs being weird, falling back to web api")
		from urllib import request
		with request.urlopen("https://beta.mkb.gorlem.ml/api/docs") as url:
			mkbjson = json.loads(url.read().decode())
			print("MKBdocs (Online) loaded")
	except:
		print("MKBdocs offline and online both being weird")

functions = []

def plugin_loaded():
	global settings
	settings = sublime.load_settings("MKB.sublime-settings")
	print("Settings loaded")
	global globalvars
	globalvars = []

def config(key):
	if settings.get(key):
		return settings.get(key)

def viewlines():
	filelines = sublime.active_window().active_view().substr(sublime.Region(0, len(sublime.active_window().active_view()))).split("\n")
	if config("indent_expand"):
		string = ""
		for l in filelines:
			l = l.strip()
			if l.endswith(";"):
				string += l
			else:
				string += l + ";"
		return string
	else:
		return "".join(filelines)

def load(words):
	if words.isalpha():
		for i in mkbjson:
			if words.lower() == i["name"].lower():
				return i


class mkbindentation(sublime_plugin.TextCommand):
	def run(self, edit):
		if self.view.match_selector(0, "source.mkb"):
			mkbindent.openfile(self, True)

class mkbindent(sublime_plugin.ViewEventListener):

	def on_pre_save(self):
		self.view.erase_regions("mkblinter")
		if self.view.match_selector(0, "source.mkb"):

			if config("enable_indent") and config("ask_before_indent"):
				if sublime.ok_cancel_dialog("Auto indent code?", "Indent"):
					self.openfile(self, True)
			elif config("enable_indent"):
				self.openfile(self, True)

	def on_post_save(self):
		variables = re.findall("(@(#|&)?[a-z_\-1-9]+)",viewlines())
		if variables:
			for i in variables:
				if i[0] not in globalvars:
					globalvars.append(i[0])

	def openfile(self, indent):
		indentedlines = Indenter(code=viewlines())
		if indent:
			mkbindent.lineindentermode(self, indentedlines.indent(debug=False))
		else:
			results = indentedlines.indent(debug=True)

	def lineindentermode(self, args):
		if config("fancy_indent") != None and config("fancy_indent") != 0:
			self.view.run_command("lineindenter", {"args": [args[0],0]})
		else:
			self.view.run_command("lineindenter", {"args": [args[0],-1]})

	def on_selection_modified(self):
		if config("auto_linting"):
			self.view.run_command("mkbdebug2")
		if config("functions_underline"):
			self.view.run_command("functions_syntax")

class lineindenter(sublime_plugin.TextCommand):
	def run(self, edit, args):
		if self.view.match_selector(0, "source.mkb"):
			count = args[1]
			if count == -1:
				self.view.replace(edit, sublime.Region(0, len(self.view)), "\n".join(args[0]))
				if config("message_after_indenting"):
					sublime.message_dialog("Finished Indenting!")
			else:
				regions = self.view.split_by_newlines(sublime.Region(0, len(self.view)))
				if self.view.substr(regions[count]) != args[0][count]:
					self.view.replace(edit, regions[count], args[0][count])
				count += 1
				if count == len(args[0]) - 1:
					if config("message_after_indenting"):
						sublime.message_dialog("Finished Indenting!")
				elif self.view.substr(regions[count]) == args[0][count]:
					sublime.set_timeout_async(lambda: self.view.run_command("lineindenter", {"args": [args[0],count]}),0)
				elif count < len(args[0]) - 1:
					sublime.set_timeout_async(lambda: self.view.run_command("lineindenter", {"args": [args[0],count]}),config("fancy_indent"))

# Indenter by Federal
class Indenter:

	def __init__(self, code): # Pass the code its self instead of lines
		filelines = sublime.active_window().active_view().substr(sublime.Region(0, len(sublime.active_window().active_view()))).split("\n")
		if config("indent_expand"):
			string = ""
			for l in filelines:
				l = l.strip()
				if l.endswith(";"):
					string += l
				else:
					string += l + ";"
			splitted = string.split(";")

			# Splits line properly and excludes semicolons in strings
			temp = ""
			lines = []
			for i in splitted:
				temp += ("" if temp == "" else ";") + i

				if temp.replace("\\\\","").replace("\\\"","").count("\"") % 2 == 0:
					lines.append(temp)
					temp = ""
			splitted = lines

		else:
			splitted = filelines

		emptycount = 0
		for s in splitted[::-1]:
			if s == "":
				emptycount += 1
			else:
				break
		if emptycount == 0:
			self.lines = splitted[:]
		else:
			self.lines = splitted[:-emptycount]
		self.lines.append("")
		self.stack = [] # It stores the searching endings
		self.indented = []
		self.level = 0
		self.blocks = {
			"if":		["else", "endif"],
			"ifnot":		["else", "endif"],
			"elseif":	["else", "endif"],
			"elseifnot":	["else", "endif"],
			"else":		["endif"],
			"for":		["next"],
			"foreach":	["next"],
			"do":		["until", "while", "loop"],
			"unsafe":	["endunsafe"],
			"pollevent":["next"],
			"switch":	["endswitch"],
			# "case":		["case", "default", "endswitch"],
			# "default" :	["endswitch"],
			"function": ["endfunction"]
		}
		self.openings = "IF|IFNOT|ELSEIF|ELSEIFNOT|ELSE|FOR|DO|UNSAFE|POLLEVENT|SWITCH|FUNCTION"
		self.lintlines = []
		self.extra = 0

		if config("extra_indent"):
			self.blocks["$${"] = ["}\$\$"]
			self.openings += "|\\$\\${"

	def related_command(line, pattern):
		# match = re.match(r"^({})(\b|$).*".format(pattern), line, re.IGNORECASE)
		match = re.match(r"^({}\w*?)".format(pattern), line, re.IGNORECASE)
		return None if not match else match.groups()[0]

	def indent_line(self, line):
		# print(self.extra)
		# print(line)
		if line and config("semicolon_end") and line != "$${" and line != "}$$":
			self.indented.append(config("indent_character") * (self.level+self.extra) + line + ";")
		else:
			self.indented.append(config("indent_character") * (self.level+self.extra) + line) # Inserts a line into the indented output list lines

	def indent(self, debug):
		count = 0
		errorbool = False
		for line in self.lines:
			count += 1
			l = line.strip()
			closed = False
			if self.level and Indenter.related_command(l, self.stack[-1]): # Checks if the line corresponds to an ending
				if Indenter.related_command(l, self.stack[-1]) == "endswitch":
					# self.level -= 1s
					self.extra -= 1
				self.stack.pop()
				self.level -= 1 # Forwards the indentation
				self.indent_line(l)
				closed = True
			elif Indenter.related_command(l, self.openings) is None:
				teststring = re.match("elseif|elseifnot|else|endif|next|until|while|loop|endunsafe|endswitch|function", line, re.IGNORECASE)
				if teststring is not None and debug:
					print(" Error found on line "+str(count)+": "+line)
					errorbool = True
			command = Indenter.related_command(l, self.openings) # Get tries to extract a block opening word
			if command is not None:
				self.stack.append("|".join(self.blocks[command.lower()]))
				if not closed: # If the block was already closed, there's no reason to repeat the line
					self.indent_line(l)
					if "switch" in l:
						self.extra += 1
						# print(self.extra)
				self.level += 1 # Backwards the indentation
				errorstring = " Error found on line "+str(count)+": "+line
				self.lintlines.append(line)
				# print(line)
				# print()
			elif not closed:
				if "case" in l or "default" in l:
					self.extra -= 1
					self.indent_line(l)
					self.extra += 1
				else:
					self.indent_line(l) # Insert a standard (no-command) line

		# print(self.level)
		if self.level != 0 and debug:
			# print(self.level)
			print(errorstring)
		elif not errorbool and debug:
			print(" No stack errors")
		return (self.indented, self.lintlines)
		# return '\n'.join(self.indented).replace("$${;", "$${").replace("}$$;", "}$$") # List to text + some adjustments

class hoverinfo(sublime_plugin.ViewEventListener):
	def on_hover(self, point, hover_zone):
		if self.view.match_selector(0, "source.mkb"):
			hoverword = self.view.substr(self.view.word(point))
			data = load(hoverword)
			if data:
				mkbhint.showpopup(self, data, point, False)
			else:
				mkbhint.showpopup(self, data, point, False)

class mkbvariables(sublime_plugin.TextCommand):
	def run(self, edit):
		if self.view.match_selector(0, "source.mkb"):
			variables = re.findall("(set\(|SET\()?(@&|@#|&|#|@)([a-z_\-1-9]+)",viewlines())
			global var
			var = []
			for i in variables:
				if i[1]+i[2] not in var:
					var.append(i[1]+i[2])
			for i in globalvars:
				if i not in var:
					var.append(i)
			sublime.Window.show_quick_panel(sublime.active_window(), var, self.on_done, sublime.KEEP_OPEN_ON_FOCUS_LOST, 0, None)
	
	def on_done(self, index):
		if index != -1:
			sublime.active_window().run_command("insert", {"characters": var[index]})

class mkbhint(sublime_plugin.TextCommand):
	def run(self, edit, event=None):
		if self.view.match_selector(0, "source.mkb"):
			if event:
				pos = self.view.window_to_text((event["x"],event["y"]))
			word = self.view.substr(self.view.word(pos))
			data = load(word)
			if data:
				self.showpopup(data, pos, True)

	def want_event(self):
		return True

	def showpopup(self, originaldata, pos, override):
		data = deepcopy(originaldata)
		if data and (config("show_hints") or override):
			data["extendedName"] = data["extendedName"].replace("&", "&amp;")
			data["extendedName"] = data["extendedName"].replace("<", "&lt;").replace(">", "&gt;").replace("\\\"", "&quot;")
			data["description"] = data["description"].replace("&", "&amp;")
			data["description"] = data["description"].replace("<", "&lt;").replace(">", "&gt;").replace("\\\"", "&quot;")
			data["description"] = data["description"].replace("\n\n\n", "<br><br>").replace("\n", "<br>")

			while True:
				match = re.search("\`([^\`]*?)\`",data["extendedName"])
				if match:
					data["extendedName"] = re.sub("\`([^\`]*?)\`","<u>{}</u>".format(match.groups(1)[0]),data["extendedName"],1)
				else:
					break

			while True:
				match = re.search("\`([^\`]*?)\`",data["description"])
				if match:
					data["description"] = re.sub("\`([^\`]*?)\`","<u>{}</u>".format(match.groups(1)[0]),data["description"],1)
				else:
					break

			if data["example"]:
				data["example"] = data["example"].replace("&", "&amp;")
				data["example"] = data["example"].replace("<", "&lt;").replace(">", "&gt;").replace("\\\"", "&quot;")
				data["example"] = data["example"].replace("\n\n\n", "<br><br>").replace("\n", "<br>")
				example = "<br><b>Example:</b><br>"
			else:
				data["example"] = ""
				example = ""

			html = """
				<b>{}</b>
				<a href="">Open wiki</a>
				<br>
				<strong>Type: {} ({})</strong>
				<br>
				<i>{}</i>
				<br>
				<small>{}{}</small>
				""".format(data["extendedName"],data["type"],data["category"],data["description"],example,data["example"],)
			if data != None:
				page = data["resource"].replace("api", "")
				linkstring = "https://beta.mkb.gorlem.ml{}".format(str(page)[1:])
				self.view.show_popup(html, sublime.COOPERATE_WITH_AUTO_COMPLETE|sublime.HIDE_ON_MOUSE_MOVE_AWAY, pos, self.view.viewport_extent()[0], self.view.line_height()*config("popup_line_height")+4, lambda link: webbrowser.get(using=config("browser")).open(linkstring, new=2), "")

			else:
				self.view.hide_popup()

class mkbmini(sublime_plugin.TextCommand):
	def run(self, edit):
		if self.view.match_selector(0, "source.mkb"):
			string = re.sub("//.*?;", "",viewlines())
			while True:
				match1 = re.search("(?<!i)if\(([^;]*?)\);echo\(([^;]*?)\);endif(;)?",string)
				match2 = re.search("(?<!i)if\(([^;]*?)\);echo\(([^;]*?)\);else;echo\(([^;]*?)\);endif(;)?",string)
				if match1:
					original = match1.group(0).replace("\"", "\\\"").replace("(", "\(").replace(")", "\)")
					iif = "iif(" + match1.group(1) + "," + match1.group(2) + ");"
					string = re.sub(original,iif,string)
				elif match2:
					original = match2.group(0).replace("\"", "\\\"").replace("(", "\(").replace(")", "\)")
					iif = "iif(" + match2.group(1) + "," + match2.group(2) + "," + match2.group(3) + ");"
					string = re.sub(original,iif,string)
				else:
					break
			string = string.replace("$${;", "$${").replace(";}$$;", "}$$").replace(";}$$", "}$$").replace("}$$;", "}$$")
			string = string.replace(";;", ";")
			print("Minifier: ")
			print(string)
			print()
			sublime.active_window().run_command("show_panel", {"panel": "console", "toggle": True})
			if config("message_after_minifying"):
				sublime.message_dialog("Check console for minifier results")

class mkbdebug(sublime_plugin.TextCommand):
	def run(self, edit):
		if config("indent_after_linting"):
			mkbindent.openfile(self, True)
		if self.view.match_selector(0, "source.mkb"):
			self.view.erase_regions("mkblinter")
			print("\n-----------Linter-----------")
			mkbindent.openfile(self, False)
			regions = self.view.split_by_newlines(sublime.Region(0, len(self.view)))
			lines = []
			[lines.append(self.view.substr(r)) for r in regions]
			count = 0
			regionlist = self.view.get_regions("mkblinter")

			for line in lines:
				count += 1
				bracketerror = False
				bracketerror2 = False
				varerror = False
				quotserror = False

				opened = 0
				opened2 = 0
				var = False
				quots = False
				escaped = False

				for char in line:
					if escaped:
						escaped = False
					elif char == "\\":
						escaped = True
					elif char == "(" and not quots:
						opened += 1
					elif char == ")" and not quots:
						opened -= 1
					elif char == "[" and not quots:
						opened2 += 1
					elif char == "]" and not quots:
						opened2 -= 1
					elif char == "%":
						if var:
							var = False
						else:
							var = True
					elif char == "\"":
						if quots:
							quots = False
						else:
							quots = True

				if opened > 0:
					print(" "+str(opened)+" ) missing on line "+str(count))
					bracketerror = True
				if opened < 0:
					print(" "+str(-opened)+" ( missing on line "+str(count))
					bracketerror = True
				if opened2 > 0:
					print(" "+str(opened2)+" ] missing on line "+str(count))
					bracketerror2 = True
				if opened2 < 0:
					print(" "+str(-opened2)+" [ missing on line "+str(count))
					bracketerror2 = True
				if var:
					print(" 1 % missing on line "+str(count))
					varerror = True
				if quots:
					print(" 1 \" missing on line "+str(count))
					quotserror = True
				if bracketerror or bracketerror2 or varerror or quotserror:
					regionlist.append(self.view.line(self.view.text_point(count-1,0)))

			if not bracketerror and not bracketerror2:
				print(" All brackets are closed")
			if not varerror:
				print(" All variables are enclosed")
			if not quotserror:
				print(" All strings are enclosed")
			self.view.add_regions("mkblinter", regionlist, "invalid.mkb", "dot", sublime.DRAW_NO_FILL)
			if bracketerror or bracketerror2 or varerror or quotserror:
				print("\n You should run the linter\n again after fixing errors")
			print("----------------------------")
			if config("message_after_linting"):
				sublime.message_dialog("Check console for linting results")
			sublime.active_window().run_command("show_panel", {"panel": "console", "toggle": True})

class mkbdebug2(sublime_plugin.TextCommand):
	def run(self, edit):
		if self.view.match_selector(0, "source.mkb"):
			self.view.erase_regions("mkblinter")
			regions = self.view.split_by_newlines(sublime.Region(0, len(self.view)))
			lines = []
			[lines.append(self.view.substr(r)) for r in regions]
			count = 0
			regionlist = self.view.get_regions("mkblinter")

			for line in lines:
				count += 1
				bracketerror = False
				bracketerror2 = False
				varerror = False
				quotserror = False

				opened = 0
				opened2 = 0
				var = False
				quots = False
				escaped = False

				for char in line:
					if escaped:
						escaped = False
					elif char == "\\":
						escaped = True
					elif char == "(" and not quots:
						opened += 1
					elif char == ")" and not quots:
						opened -= 1
					elif char == "[" and not quots:
						opened2 += 1
					elif char == "]" and not quots:
						opened2 -= 1
					elif char == "%":
						if var:
							var = False
						else:
							var = True
					elif char == "\"":
						if quots:
							quots = False
						else:
							quots = True

				if opened != 0 or opened2 != 0 or var or quots:
					regionlist.append(self.view.line(self.view.text_point(count-1,0)))

			self.view.add_regions("mkblinter", regionlist, "invalid.mkb", "dot", sublime.DRAW_NO_FILL)

class mkbcase1(sublime_plugin.TextCommand):
	def run(self, edit):
		if self.view.match_selector(0, "source.mkb"):
			text = viewlines().split(";")
			count = 0
			while count < len(text):
				matches = re.findall("^[\t ]*(\/\/)?([a-zA-Z]+)(\(|;|$)", text[count])
				if matches != []:
					text[count] = text[count].replace(matches[0][1], matches[0][1].upper(), 1)
				count += 1
			self.view.replace(edit, sublime.Region(0, len(self.view)), "\n".join(text[:-1]));
			mkbindent.openfile(self, True)

class mkbcase2(sublime_plugin.TextCommand):
	def run(self, edit):
		if self.view.match_selector(0, "source.mkb"):
			text = viewlines().split(";")
			count = 0
			while count < len(text):
				matches = re.findall("^[\t ]*(\/\/)?([a-zA-Z]+)(\(|;|$)", text[count])
				if matches != []:
					text[count] = text[count].replace(matches[0][1], matches[0][1].lower(), 1)
				count += 1
			self.view.replace(edit, sublime.Region(0, len(self.view)), "\n".join(text[:-1]));
			mkbindent.openfile(self, True)

class mkbcase3(sublime_plugin.TextCommand):
	def run(self, edit):
		if self.view.match_selector(0, "source.mkb"):
			text = viewlines().split(";")
			count = 0
			while count < len(text):
				matches = re.findall("^[\t ]*(\/\/)?([a-zA-Z]+)(\(|;|$)", text[count])
				if matches != []:
					text[count] = text[count].replace(matches[0][1], matches[0][1].capitalize(), 1)
				count += 1
			self.view.replace(edit, sublime.Region(0, len(self.view)), "\n".join(text[:-1]));
			mkbindent.openfile(self, True)

class mkbdeco(sublime_plugin.TextCommand):
	def run(self, edit):
		if self.view.match_selector(0, "source.mkb"):

			text = viewlines().split(";")
			count = 0
			while count < len(text):
				matches = re.findall("^[\t ]*(\/\/)?([a-zA-Z]+)(\(|;|$)", text[count])
				if matches != []:
					text[count] = text[count].replace(matches[0][1], matches[0][1].lower())
				count += 1

			count = 0
			while count < len(text):
				if text[count] != "" and text[count] != "$${" and text[count] != "}$$":
					text[count] += ";"
				count += 1
			self.view.replace(edit, sublime.Region(0, len(self.view)), "\n".join(text[:-1]));


			regions = []
			filelines = sublime.active_window().active_view().substr(sublime.Region(0, len(sublime.active_window().active_view()))).split("\n")
			string = ""
			for l in filelines:
				if l.endswith(";"):
					string += l
				else:
					string += l + ";"
			count = 0
			for match in re.finditer("\$\$\{|;+|(<|>|==|!=|>=|<=|&&|\|\||\+|\-|\*|\/|=|:=)", string):
				if match.group() == "$${":
					count -= 1
				elif match.group().startswith(";"):
					count += 1
				else:
					# print(match.span())
					regions.append(sublime.Region(match.start()+count, match.end()+count))
					self.view.add_regions("mkblinter", regions, "invalid.mkb", "dot", sublime.DRAW_NO_FILL)

			# mkbindent.openfile(self, True)

class jump_up(sublime_plugin.WindowCommand):
	def run(self):
		file = self.window.active_view().substr(sublime.Region(0, len(sublime.active_window().active_view()))).split("\n")
		point = self.window.active_view().sel()[-1].b
		line = self.window.active_view().substr(self.window.active_view().full_line(point))
		line_num = self.window.active_view().rowcol(point)[0]
		tabs = re.search("^\s*", line).group()
		reg = self.window.active_view().split_by_newlines(sublime.Region(0, len(sublime.active_window().active_view())))
		count = line_num - 1
		while count >= 0:
			if re.match("^{}[^\s]".format(tabs), file[count]):
				self.window.active_view().run_command('_sublime_linter_move_cursor', {'point': reg[count].a+len(tabs)})
				break
			count -= 1

class jump_down(sublime_plugin.WindowCommand):
	def run(self):
		file = self.window.active_view().substr(sublime.Region(0, len(sublime.active_window().active_view()))).split("\n")
		point = self.window.active_view().sel()[-1].b
		line = self.window.active_view().substr(self.window.active_view().full_line(point))
		line_num = self.window.active_view().rowcol(point)[0]
		tabs = re.search("^\s*", line).group()
		reg = self.window.active_view().split_by_newlines(sublime.Region(0, len(sublime.active_window().active_view())))
		count = line_num
		while count <= len(file) - 2:
			if re.match("^{}[^\s]".format(tabs), file[count+1]):
				self.window.active_view().run_command('_sublime_linter_move_cursor', {'point': reg[count].b+1+len(tabs)})
				break
			count += 1

class mkbwiki(sublime_plugin.TextCommand):
	def run(self, edit):
		array = ["{} ({})".format(i["name"], i["type"]) for i in mkbjson]
		sublime.Window.show_quick_panel(sublime.active_window(), array, self.on_done, sublime.KEEP_OPEN_ON_FOCUS_LOST, 0, None)

	def on_done(self, index):
		if index != -1:
			array = ["Open Wiki for {}".format(mkbjson[index]["name"])]
			for key, value in mkbjson[index].items():
				if value != None:
					array.append("{}: {}".format(str(key).title(),value))

			sublime.Window.show_quick_panel(sublime.active_window(), array, self.on_done2, sublime.KEEP_OPEN_ON_FOCUS_LOST, 0, None)
		global wikiindex
		wikiindex = index

	def on_done2(self, index):
		if index == -1:
			sublime.active_window().run_command("mkbwiki")
		elif index == 0:
			page = mkbjson[wikiindex]["resource"].replace("api", "")
			linkstring = "https://beta.mkb.gorlem.ml{}".format(str(page)[1:])
			webbrowser.get(using=config("browser")).open(linkstring, new=2)
		else:
			# print(list(mkbjson[wikiindex].keys())[index])
			# key = list(mkbjson[wikiindex].keys())[index]

			array = []
			for key, value in mkbjson[wikiindex].items():
				if value != None:
					array.append([key, value])

			print("{}: {}".format(array[index-1][0].title(), array[index-1][1]))
			sublime.active_window().run_command("show_panel", {"panel": "console", "toggle": True})

			# array = ["{} ({})".format(i["name"], i["type"]) for i in mkbjson]
			# sublime.Window.show_quick_panel(sublime.active_window(), array, self.on_done, sublime.KEEP_OPEN_ON_FOCUS_LOST, 0, None)

			array = ["Open Wiki for {}".format(mkbjson[wikiindex]["name"])]
			for key, value in mkbjson[wikiindex].items():
				if value != None:
					array.append("{}: {}".format(str(key).title(),value))

			sublime.Window.show_quick_panel(sublime.active_window(), array, self.on_done2, sublime.KEEP_OPEN_ON_FOCUS_LOST, 0, None)

class functions_syntax(sublime_plugin.TextCommand):
	def run(self, edit):
		if self.view.match_selector(0, "source.mkb"):
			global functions
			functions = []
			self.view.erase_regions("mkbfunctions")
			regions = self.view.split_by_newlines(sublime.Region(0, len(self.view)))
			lines = [self.view.substr(r) for r in regions]
			count = 0
			regionlist = self.view.get_regions("mkbfunctions")

			for line in lines:
				count += 1
				function_name = re.match("^\s*?function (\w*?)\(", line)
				if function_name != None:
					functions.append(function_name.group(1))

				string = "|".join(functions)
				string = "^\s*?(call\()?(function )?{}( |,|\(|\))".format(string)
				function_call = re.match(string, line)
				if function_call != None:
					# print(function_call.group(1))
					if function_call.group(1) != None:
						regionlist.append(self.view.word(self.view.text_point(count-1,5+line.count("\t"))))
					elif function_call.group(2) != None:
						regionlist.append(self.view.word(self.view.text_point(count-1,9+line.count("\t"))))
					else:
						regionlist.append(self.view.word(self.view.text_point(count-1,0+line.count("\t"))))


			self.view.add_regions("mkbfunctions", regionlist, "meta.function.mkb", "", sublime.DRAW_NO_FILL|sublime.DRAW_NO_OUTLINE|sublime.DRAW_SOLID_UNDERLINE)

class mkb_goto_definition(sublime_plugin.TextCommand):

	def want_event(self):
		return True

	def run(self, edit, event=None):
		if self.view.match_selector(0, "source.mkb"):
			if event:
				pos = self.view.window_to_text((event["x"],event["y"]))
				word = self.view.substr(self.view.word(pos))
				if word != "":
					regions = self.view.split_by_newlines(sublime.Region(0, len(self.view)))
					lines = [self.view.substr(r) for r in regions]
					reg = self.view.split_by_newlines(sublime.Region(0, len(sublime.active_window().active_view())))
					count = 0

					for line in lines:
						function_name = re.match("^\s*?function {}\(".format(word), line)
						if function_name != None:
							self.view.run_command('_sublime_linter_move_cursor', {'point': reg[count].a+9+line.count("\t")})
							break
						count += 1
				