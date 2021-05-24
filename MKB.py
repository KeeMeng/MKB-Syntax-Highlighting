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
			"elseif":	["else", "endif"],
			"else":		["endif"],
			"for":		["next"],
			"foreach":	["next"],
			"do":		["until", "while", "loop"],
			"unsafe":	["endunsafe"],
			"pollevent":["next"],
			"switch":	["endswitch"],
			"case":		["case", "default", "endswitch"],
			"default" :	["endswitch"],
			"function": ["endfunction"]
		}
		self.openings = "IF|ELSEIF|ELSE|FOR|DO|UNSAFE|POLLEVENT|SWITCH|CASE|DEFAULT|FUNCTION"
		self.lintlines = []

		if config("extra_indent"):
			self.blocks["$${"] = ["}\$\$"]
			self.openings += "|\\$\\${"

	def related_command(line, pattern):
		# match = re.match(r"^({})(\b|$).*".format(pattern), line, re.IGNORECASE)
		match = re.match(r"^({}\w*?)".format(pattern), line, re.IGNORECASE)
		return None if not match else match.groups()[0]

	def indent_line(self, line):
		if line and config("semicolon_end") and line != "$${" and line != "}$$":
			self.indented.append(config("indent_character") * self.level + line + ";")
		else:
			self.indented.append(config("indent_character") * self.level + line) # Inserts a line into the indented output list lines

	def indent(self, debug):
		count = 0
		errorbool = False
		for line in self.lines:
			count += 1
			l = line.strip()
			closed = False
			if self.level and Indenter.related_command(l, self.stack[-1]): # Checks if the line corresponds to an ending
				if Indenter.related_command(l, self.stack[-1]) == "endswitch":
					self.level -= 1
				self.stack.pop()
				self.level -= 1 # Forwards the indentation
				self.indent_line(l)
				closed = True
			elif Indenter.related_command(l, self.openings) is None:
				teststring = re.match("elseif|else|endif|next|until|while|loop|endunsafe|endswitch|case|default|function", line, re.IGNORECASE)
				if teststring is not None and debug:
					print(" Error found on line "+str(count)+": "+line)
					errorbool = True
			command = Indenter.related_command(l, self.openings) # Get tries to extract a block opening word
			if command is not None:
				self.stack.append("|".join(self.blocks[command.lower()]))
				if not closed: # If the block was already closed, there's no reason to repeat the line
					self.indent_line(l)
				self.level += 1 # Backwards the indentation
				errorstring = " Error found on line "+str(count)+": "+line
				self.lintlines.append(line)
				# print(line)
				# print()
			elif not closed:
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
							self.view.run_command('_sublime_linter_move_cursor', {'point': reg[count].a+9})
							break
						count += 1
				


# 1000+ Lines of auto complete below!!
class mkbcompletions(sublime_plugin.EventListener):
	def on_query_completions(self, view, prefix, locations):
		if view.match_selector(view.line(locations[0]).a, "comment.mkb"):
			return ([],sublime.INHIBIT_EXPLICIT_COMPLETIONS)
		elif view.match_selector(0, "source.mkb") and config("autocomplete_caps"):
			return sublime.CompletionList([
				sublime.CompletionItem(trigger="IF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="…ENDIF", details="Executes if the &#60;condition&#62; evaluates to true", completion="IF(${1:<condition>});\n	$2\nENDIF;\n$3"),
				sublime.CompletionItem(trigger="IFBEGINSWITH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET,  annotation="…ENDIF", details="Executes if the &#60;haystack&#62; starts with the &#60;needle&#62;",completion="IFBEGINSWITH(${1:<haystack>},${2:<needle>});\n	$3\nENDIF;\n$4"),
				sublime.CompletionItem(trigger="IFENDSWITH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="…ENDIF", details="Executes if the &#60;haystack&#62; ends with the &#60;needle&#62;", completion="IFENDSWITH(${1:<haystack>},${2:<needle>});\n	$3\nENDIF;\n$4"),
				sublime.CompletionItem(trigger="IFCONTAINS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="…ENDIF", details="Executes if the &#60;haystack&#62; contains the &#60;needle&#62;", completion="IFCONTAINS(${1:<haystack>},${2:<needle>});\n	$3\nENDIF;\n$4"),
				sublime.CompletionItem(trigger="IFMATCHES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="…ENDIF", details="Executes if the &#60;subject&#62; matches the &#60;pattern&#62;", completion="IFMATCHES(${1:<subject>},${2:<pattern>},&${3:[target]},${4:[group]});\n	$5\nENDIF;\n$6"),
				sublime.CompletionItem(trigger="ENDIF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="…ENDIF", details="Ends an if-clause", completion="ENDIF;\n$1"),
				sublime.CompletionItem(trigger="FOR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="FOR(var,start,end)…NEXT", details="Begins a for loop", completion="FOR(#${1:<var>},${2:<start>},${3:<end>});\n	$4\nNEXT;\n$5"),
				sublime.CompletionItem(trigger="FOR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="FOR(var = start to end)…NEXT", details="Begins a for loop", completion="FOR(#${1:<var>} = ${2:<start>} to ${3:<end>});\n	$4\nNEXT;\n$5"),
				sublime.CompletionItem(trigger="FOR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="FOR(var = start to end step)…NEXT", details="Begins a for loop", completion="FOR(#${1:<var>} = ${2:<start>} to ${3:<end>} step ${4:<step>});\n	$5\nNEXT;\n$6"),
				sublime.CompletionItem(trigger="FOREACH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="FOREACH(iterator)…NEXT", details="Begins a loop over the specified iterator", completion="FOREACH(${1:<iterator>});\n	$2\nNEXT;\n$3"),
				sublime.CompletionItem(trigger="FOREACH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="FOREACH(array,content,index)…NEXT", details="Begins a loop over the specified iterator", completion="FOREACH(${1:<array>}[],${2:<content>},#${3:[index]});\n	$4\nNEXT;\n$5"),
				sublime.CompletionItem(trigger="FOREACH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="FOREACH(array as content)…NEXT", details="Begins a loop over the specified iterator", completion="FOREACH(${1:<array>}[] as &${2:<content>});\n	$3\nNEXT;\n$4"),
				sublime.CompletionItem(trigger="FOREACH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="FOREACH(array as index =&#62; content)…NEXT", details="Begins a loop over the specified iterator", completion="FOREACH(${1:<array>}[] as #${2:<index>} => ${3:<content>});\n	$4\nNEXT;\n$5"),
				sublime.CompletionItem(trigger="DO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="…LOOP", details="Begins a loop", completion="DO(${1:[count]});\n	$2\nLOOP;$3"),
				sublime.CompletionItem(trigger="DO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="…WHILE", details="Begins a loop", completion="DO(${1:[count]});\n	$2\nWHILE(${3:<condition>});$4"),
				sublime.CompletionItem(trigger="DO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="…UNTIL", details="Begins a loop", completion="DO(${1:[count]});\n	$2\nUNTIL(${3:<condition>});$4"),
				sublime.CompletionItem(trigger="ELSE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Executes if no if-clause before evaluated to true", completion="ELSE;\n	$1"),
				sublime.CompletionItem(trigger="ELSEIF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Executes if the evaluates to true and no if-clause before evaluated to true", completion="ELSEIF(${1:<condition>});\n	$2"),
				sublime.CompletionItem(trigger="LOOP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Closes a do loop", completion="LOOP;\n$1"),
				sublime.CompletionItem(trigger="WHILE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the &#60;condition&#62; is not met", completion="WHILE(${1:<condition>});\n$2"),
				sublime.CompletionItem(trigger="UNTIL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the &#60;condition&#62; is met", completion="UNTIL(${1:<condition>});\n$2"),
				sublime.CompletionItem(trigger="ELSEIFBEGINSWITH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Executes if the &#60;haystack&#62; starts with the &#60;needle&#62; and no if-clause before evaluated to true", completion="ELSEIFBEGINSWITH(${1:<haystack>},${2:<needle>});\n	$3"),
				sublime.CompletionItem(trigger="ELSEIFCANHARVESTBLOCK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Executes if the &#60;blockid&#62; can currently be harvested and no if-clause before evaluated to true", completion="ELSEIFCANHARVESTBLOCK(${1:<blockid>});\n	$2"),
				sublime.CompletionItem(trigger="ELSEIFCONTAINS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Executes if the &#60;haystack&#62; contains the &#60;needle&#62; and no if-clause before evaluated to true", completion="ELSEIFCONTAINS(${1:<haystack>},${2:<needle>});\n	$3"),
				sublime.CompletionItem(trigger="ELSEIFENCHANTED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Executes if the item at &#60;slot&#62; is enchanted and no if-clause before evaluated to true", completion="ELSEIFENCHANTED(${1:<slot>},&${2:[item]},#${3:[stacksize]},#${4:[datavar]},&${5:[nbt]});\n	$6"),
				sublime.CompletionItem(trigger="ELSEIFENDSWITH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Executes if the &#60;haystack&#62; ends with the &#60;needle&#62; and no if-clause before evaluated to true", completion="ELSEIFENDSWITH(${1:<haystack>},${2:<needle>});\n	$3"),
				sublime.CompletionItem(trigger="ELSEIFFILEEXIST", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Executes if the file exists at &#60;path&#62; and no if-clause before evaluated to true", completion="ELSEIFFILEEXISTS(${1:<path>},${2:[expression if file should be created if missing]});\n	$3"),
				sublime.CompletionItem(trigger="ELSEIFININV", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Executes if the &#60;items&#62; are in the inventory and no if-clause before evaluated to true", completion="ELSEIFININV(${1:[mode]},${2:<items>});\n	$3"),
				sublime.CompletionItem(trigger="ELSEIFINVISFULL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Executes if the inventory is full and no if-clause before evaluated to true", completion="ELSEIFINVISFULL(${1:[item]});\n	$2"),
				sublime.CompletionItem(trigger="ELSEIFMATCHES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Executes if the &#60;subject&#62; matches the &#60;pattern&#62; and no if-clause before evaluated to true", completion="ELSEIFMATCHES(${1:<subject>},${2:<pattern>},&${3:[target]},${4:[group]});\n	$5"),
				sublime.CompletionItem(trigger="WHILEBEGINSWITH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if &#60;haystack&#62; does not start with the &#60;needle&#62;", completion="WHILEBEGINSWITH(${1:<haystack>},${2:<needle>});\n$3"),
				sublime.CompletionItem(trigger="WHILECANHARVESTBLOCK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the &#60;blockid&#62; cannot currently be harvested", completion="WHILECANHARVESTBLOCK(${1:<blockid>});\n$2"),
				sublime.CompletionItem(trigger="WHILECONTAINS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if &#60;haystack&#62; does not contain the &#60;needle&#62;", completion="WHILECONTAINS(${1:<haystack>},${2:<needle>});\n$3"),
				sublime.CompletionItem(trigger="WHILEENCHANTED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the item at &#60;slot&#62; is not enchanted", completion="WHILEENCHANTED(${1:<slot>},&${2:[item]},#${3:[stacksize]},#${4:[datavar]},&${5:[nbt]});\n$6"),
				sublime.CompletionItem(trigger="WHILEENDSWITH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if &#60;haystack&#62; does not end with the &#60;needle&#62;", completion="WHILEENDSWITH(${1:<haystack>},${2:<needle>});\n$3"),
				sublime.CompletionItem(trigger="WHILEFILEEXIST", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the file does not exist at &#60;path&#62;", completion="WHILEFILEEXISTS(${1:<path>},${2:[expression if file should be created if missing]});\n$3"),
				sublime.CompletionItem(trigger="WHILEININV", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the &#60;items&#62; are not in the inventory", completion="WHILEININV(${1:[mode]},${2:<items>});\n$3"),
				sublime.CompletionItem(trigger="WHILEINVISFULL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the inventory is not full", completion="WHILEINVISFULL(${1:[item]});\n$2"),
				sublime.CompletionItem(trigger="WHILEMATCHES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the &#60;subject&#62; does not match the &#60;pattern&#62;", completion="WHILEMATCHES(${1:<subject>},${2:<pattern>},&${3:[target]},${4:[group]});\n$5"),
				sublime.CompletionItem(trigger="UNTILBEGINSWITH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if &#60;haystack&#62; starts with the &#60;needle&#62;", completion="UNTILBEGINSWITH(${1:<haystack>},${2:<needle>});\n$3"),
				sublime.CompletionItem(trigger="UNTILCANHARVESTBLOCK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the &#60;blockid&#62; can currently be harvested", completion="UNTILCANHARVESTBLOCK(${1:<blockid>});\n$2"),
				sublime.CompletionItem(trigger="UNTILCONTAINS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if &#60;haystack&#62; contains the &#60;needle&#62;", completion="UNTILCONTAINS(${1:<haystack>},${2:<needle>});\n$3"),
				sublime.CompletionItem(trigger="UNTILENCHANTED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the item at &#60;slot&#62; is enchanted", completion="UNTILENCHANTED(${1:<slot>},&${2:[item]},#${3:[stacksize]},#${4:[datavar]},&${5:[nbt]});\n$6"),
				sublime.CompletionItem(trigger="UNTILENDSWITH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if &#60;haystack&#62; ends with the &#60;needle&#62;", completion="UNTILENDSWITH(${1:<haystack>},${2:<needle>});\n$3"),
				sublime.CompletionItem(trigger="UNTILFILEEXIST", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the file exists at &#60;path&#62;", completion="UNTILFILEEXISTS(${1:<path>},${2:[expression if file should be created if missing]});\n$3"),
				sublime.CompletionItem(trigger="UNTILININV", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the &#60;items&#62; are in the inventory", completion="UNTILININV(${1:[mode]},${2:<items>});\n$3"),
				sublime.CompletionItem(trigger="UNTILINVISFULL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the inventory is full", completion="UNTILINVISFULL(${1:[item]});\n$2"),
				sublime.CompletionItem(trigger="UNTILMATCHES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Exits do loop if the &#60;subject&#62; matches the &#60;pattern&#62;", completion="UNTILMATCHES(${1:<subject>},${2:<pattern>},&${3:[target]},${4:[group]});\n$5"),
				sublime.CompletionItem(trigger="UNSAFE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="…ENDUNSAFE", details="Begins an unsafe block with maximum executions set to &#60;executions&#62;", completion="UNSAFE(${1:<executions>});\n	$2\nENDUNSAFE;\n$3"),
				sublime.CompletionItem(trigger="ENDUNSAFE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Ends an active unsafe block", completion="ENDUNSAFE;\n$1"),
				sublime.CompletionItem(trigger="FUNCTION: print", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_FUNCTION, details="custom function definition to print &#60;text&#62;", completion="FUNCTION print(&text);\n\tlog(\"%&text%\");\nendfunction;\n\nprint(${1:<text>});\n"),
				sublime.CompletionItem(trigger="PRINT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="custom function call to print &#60;text&#62;", completion="PRINT(${1:<text>});"),
				sublime.CompletionItem(trigger="GETITEMINFO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(AEI Module)", details="Gets information about the specified slot", completion="GETITEMINFO(${1:<slot>},&${2:[idvar]},#${3:[stacksize]},#${4:[datavar]},&${5:[display]},&${6:[lore]});"),
				sublime.CompletionItem(trigger="GETGUINAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(AEI Module)", details="Gets the display name of the current GUI", completion="GETGUINAME(&${1:<name>});"),
				sublime.CompletionItem(trigger="INVFULL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(AEI Module)", details="Returns empty or full in the string defined", completion="INVFULL(&${1:<string>});"),
				sublime.CompletionItem(trigger="MODULEAEI", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(AEI Module)", details="Returns true if the module is installed", completion="%MODULEAEI%"),
				sublime.CompletionItem(trigger="SETANVILTEXT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(anvilRename Module)", details="set name to string", completion="SETANVILTEXT(${1:<string>});"),
				sublime.CompletionItem(trigger="MODULEANVIL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(anvilRename Module)", details="Returns true if the module is installed", completion="%MODULEANVIL%"),
				sublime.CompletionItem(trigger="BARITONE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Runs any baritone command", completion="BARITONE(${1:<command>});"),
				sublime.CompletionItem(trigger="GOTO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Pathfinds to specified coordinates", completion="GOTO(${1:<x>},${2:<y>},${3:<z>});"),
				sublime.CompletionItem(trigger="SETTING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Changes baritone setting", completion="SETTING(${1:<settingname>},${2:<value>});"),
				sublime.CompletionItem(trigger="CANCEL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Cancels current process", completion="CANCEL();"),
				sublime.CompletionItem(trigger="PAUSE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Pauses current process", completion="PAUSE();"),
				sublime.CompletionItem(trigger="RESUME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Resumes current process", completion="RESUME();"),
				sublime.CompletionItem(trigger="MINE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Searchs and mines provied block", completion="MINE(${1:<blockname>});"),
				sublime.CompletionItem(trigger="FARM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Farms near by crops toggle replant", completion="FARM();"),
				sublime.CompletionItem(trigger="SELSTART", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Sets pos1 of selection", completion="SELSTART(${1:<x>},${2:<y>},${3:<z>});"),
				sublime.CompletionItem(trigger="SELEND", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Sets pos2 of selection", completion="SELEND(${1:<x>},${2:<y>},${3:<z>});"),
				sublime.CompletionItem(trigger="SELCLEAR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Clears selections", completion="SELCLEAR();"),
				sublime.CompletionItem(trigger="SELREPLACE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(BaritoneAddon Module)", details="Replace specified block with replacement block", completion="SELREPLACE(${1:<blocktoreplace>},${2:<replacementblock>});"),
				sublime.CompletionItem(trigger="BARITONE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="True if baritone is running any process", completion="%BARITONE%"),
				sublime.CompletionItem(trigger="PATHFINDING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="True if baritone is pathfinding to position", completion="%PATHFINDING%"),
				sublime.CompletionItem(trigger="FARMING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="True if baritone is running the process #farm", completion="%FARMING%"),
				sublime.CompletionItem(trigger="MINING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="True if baritone is running the process #mine", completion="%MINING%"),
				sublime.CompletionItem(trigger="FOLLOWING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="True if baritone is running the process #follow", completion="%FOLLOWING%"),
				sublime.CompletionItem(trigger="BUILDING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="True if baritone is running a build process", completion="%BUILDING%"),
				sublime.CompletionItem(trigger="ALLOWBREAK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="Allow Baritone to break blocks", completion="%ALLOWBREAK%"),
				sublime.CompletionItem(trigger="ALLOWPLACE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="Allow Baritone to place blocks", completion="%ALLOWPLACE%"),
				sublime.CompletionItem(trigger="ALLOWSPRINT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="Allow Baritone to sprint", completion="%ALLOWSPRINT%"),
				sublime.CompletionItem(trigger="ALLOWPARKOUR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="Allow Baritone to parkour", completion="%ALLOWPARKOUR%"),
				sublime.CompletionItem(trigger="ALLOWINVENTORY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="Allow Baritone to move items in your inventory to your hotbar", completion="%ALLOWINVENTORY%"),
				sublime.CompletionItem(trigger="ALLOWWALKONBOTTOMSLAB", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="Slab behavior is complicated, disable this for higher path reliability", completion="%ALLOWWALKONBOTTOMSLAB%"),
				sublime.CompletionItem(trigger="ALLOWWATERBUCKETFALL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="Allow Baritone to fall arbitrary distances and place a water bucket beneath it", completion="%ALLOWWATERBUCKETFALL%"),
				sublime.CompletionItem(trigger="BLOCKBREAKADDITIONALMENTPENALTY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="This is just a tiebreaker to make it less likely to break blocks if it can avoid it", completion="%BLOCKBREAKADDITIONALMENTPENALTY%"),
				sublime.CompletionItem(trigger="BLOCKPLACEMENTPENALTY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="It doesn't actually take twenty ticks to place a block, this cost is so high because we want to generally conserve blocks which might be limited", completion="%BLOCKPLACEMENTPENALTY%"),
				sublime.CompletionItem(trigger="BLOCKREACHDISTANCE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="Block reach distance", completion="%BLOCKREACHDISTANCE%"),
				sublime.CompletionItem(trigger="MAXFALLHEIGHTNOWATER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="How far are you allowed to fall onto solid ground (without a water bucket)? 3 won't deal any damage", completion="%MAXFALLHEIGHTNOWATER%"),
				sublime.CompletionItem(trigger="FREELOOK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="Move without having to force the client-sided rotations", completion="%FREELOOK%"),
				sublime.CompletionItem(trigger="REPLANTCROPS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="Replant normal Crops while farming and leave cactus and sugarcane to regrow", completion="%REPLANTCROPS%"),
				sublime.CompletionItem(trigger="MODULEBARITONE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(BaritoneAddon Module)", details="Returns true if the module is installed", completion="%MODULEBARITONE%"),
				sublime.CompletionItem(trigger="CHAR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(charModule)", details="Returns character with unicode value", completion="&${1:<char>} = char(${2:<decimal unicode value>});"),
				sublime.CompletionItem(trigger="P", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(charModule)", details="Returns paragraph character", completion="%P%"),
				sublime.CompletionItem(trigger="DOLLAR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(charModule)", details="Returns one dollar character", completion="%DOLLAR%"),
				sublime.CompletionItem(trigger="DOLLARS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(charModule)", details="Returns two dollar character", completion="%DOLLARS%"),
				sublime.CompletionItem(trigger="MODULECHARICE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(charModule)", details="Returns true if the module is installed", completion="%MODULECHARICE%"),
				sublime.CompletionItem(trigger="GETCLIPBOARD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Clipboard Module)", details="Returns content of clipboard", completion="GETCLIPBOARD(&${1:[text]});"),
				sublime.CompletionItem(trigger="SETCLIPBOARD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Clipboard Module)", details="Sets the clipboard text", completion="SETCLIPBOARD(${1:<text>});"),
				sublime.CompletionItem(trigger="MODULECLIPBOARD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Clipboard Module)", details="Returns true if the module is installed", completion="%MODULECLIPBOARD%"),
				sublime.CompletionItem(trigger="RUN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Cloudscript Module)", details="Runs the specified script from cloudscript", completion="RUN(${1:<cloudscript>});"),
				sublime.CompletionItem(trigger="ADDANIM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Cloudscript Module)", details="Add animation", completion="ADDANIM(&${1:<array>}[]);"),
				sublime.CompletionItem(trigger="EVENT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Cloudscript Module)", details="Used by cloudscript to run an event", completion="EVENT(${1:<projectId>});"),
				sublime.CompletionItem(trigger="CHAT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Cloudscript Module)", details="Open cloudchat", completion="CHAT;"),
				sublime.CompletionItem(trigger="GETKEYBIND", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Cloudscript Module)", details="Get the macro on that key", completion="GETKEYBIND(${1:<key>},&${2:<outvar>});"),
				sublime.CompletionItem(trigger="SETKEYBIND", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Cloudscript Module)", details="Set a macro on that key", completion="SETKEYBIND(${1:<key>},${2:<some code>});"),
				sublime.CompletionItem(trigger="RETURN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Cloudscript Module)", details="End a macro and return a value", completion="RETURN(${1:<anything>});"),
				sublime.CompletionItem(trigger="SENDMESSAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Cloudscript Module)", details="Send a message on a websocket channel", completion="SENDMESSAGE(${1:<channel>},${2:<message>});"),
				sublime.CompletionItem(trigger="ENCRYPT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Cloudscript Module)", details="Encrypt the variable content", completion="ENCRYPT(&${1:<var>},${2:<16charskey>});"),
				sublime.CompletionItem(trigger="DECRYPT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Cloudscript Module)", details="Decrypt the variable content", completion="DECRYPT(&${1:<var>},${2:<16charskey>});"),
				sublime.CompletionItem(trigger="REMOVE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Cloudscript Module)", details="Remove something from array", completion="REMOVE(&${1:<array>}[],&${2:<outvar>},${3:[pos]});"),
				sublime.CompletionItem(trigger="ADDDOCS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Documentor Module)", details="Adds documentation for action", completion="ADDDOCS(${1:<name of entry>},${2:[usage]},${3:[description]},${4:[return type]});"),
				sublime.CompletionItem(trigger="LISTDOCS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Documentor Module)", details="Returns documentation of action", completion="&${1:docs}[] = listdocs(${2:[name]});"),
				sublime.CompletionItem(trigger="ENTITYTYPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Type of the entity", completion="%ENTITYTYPE%"),
				sublime.CompletionItem(trigger="ENTITYNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Name of the entity", completion="%ENTITYNAME%"),
				sublime.CompletionItem(trigger="ENTITYUUID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="UUID of the entity", completion="%ENTITYUUID%"),
				sublime.CompletionItem(trigger="ENTITYXPOSF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="X coordinates of the entity as float", completion="%ENTITYXPOSF%"),
				sublime.CompletionItem(trigger="ENTITYYPOSF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Y coordinates of the entity as float", completion="%ENTITYYPOSF%"),
				sublime.CompletionItem(trigger="ENTITYZPOSF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Z coordinates of the entity as float", completion="%ENTITYZPOSF%"),
				sublime.CompletionItem(trigger="ENTITYXPOS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="X coordinates of the entity as integer", completion="%ENTITYXPOS%"),
				sublime.CompletionItem(trigger="ENTITYYPOS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Y coordinates of the entity as integer", completion="%ENTITYYPOS%"),
				sublime.CompletionItem(trigger="ENTITYZPOS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Z coordinates of the entity as integer", completion="%ENTITYZPOS%"),
				sublime.CompletionItem(trigger="ENTITYTAG", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Tag of the entity", completion="%ENTITYTAG%"),
				sublime.CompletionItem(trigger="ENTITYDX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="X difference between the player and the entity", completion="%ENTITYDX%"),
				sublime.CompletionItem(trigger="ENTITYDY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Y difference between the player and the entity", completion="%ENTITYDY%"),
				sublime.CompletionItem(trigger="ENTITYDZ", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Z difference between the player and the entity", completion="%ENTITYDZ%"),
				sublime.CompletionItem(trigger="ENTITYDISTANCE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Distance between the player and the entity", completion="%ENTITYDISTANCE%"),
				sublime.CompletionItem(trigger="ENTITYPITCHFROMPLAYER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Pitch from the player to entity", completion="%ENTITYPITCHFROMPLAYER%"),
				sublime.CompletionItem(trigger="ENTITYYAWFROMPLAYER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Yaw from the player to entity", completion="%ENTITYYAWFROMPLAYER%"),
				sublime.CompletionItem(trigger="ENTITYNBT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="NBT of the entity", completion="%ENTITYNBT%"),
				sublime.CompletionItem(trigger="ENTITYNBTKEYS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Array of the keys of the NBT of the entity", completion="%ENTITYNBTKEYS%"),
				sublime.CompletionItem(trigger="ENTITYNBT&#60;key&#62;", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Quick way to access value of a specififc key", completion="%ENTITYNBT${1:<key>}%"),
				sublime.CompletionItem(trigger="ENTITYDIR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Fuzzy direction in which the entity is", completion="%ENTITYDIR%"),
				sublime.CompletionItem(trigger="ENTITYPITCH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Pitch where the entity is looking at", completion="%ENTITYPITCH%"),
				sublime.CompletionItem(trigger="ENTITYYAW", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Yaw where the entity is looking at", completion="%ENTITYYAW%"),
				sublime.CompletionItem(trigger="ENTITYHEALTH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Health of the entity", completion="%ENTITYHEALTH%"),
				sublime.CompletionItem(trigger="ENTITYMAXHEALTH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Max health of the entity", completion="%ENTITYMAXHEALTH%"),
				sublime.CompletionItem(trigger="ENTITYISITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="True if it's an dropped item", completion="%ENTITYISITEM%"),
				sublime.CompletionItem(trigger="ENTITYITEMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Age of the dropped item", completion="%ENTITYITEMAGE%"),
				sublime.CompletionItem(trigger="ENTITYITEMOWNER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Owner of the dropped item", completion="%ENTITYITEMOWNER%"),
				sublime.CompletionItem(trigger="ENTITYITEMTHROWER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Thrower of the dropped item", completion="%ENTITYITEMTHROWER%"),
				sublime.CompletionItem(trigger="ENTITYITEMNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Localized name of the dropped item", completion="%ENTITYITEMTHROWER%"),
				sublime.CompletionItem(trigger="ENTITYITEMUNLOCALIZEDNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Unlocalized name of the dropped item", completion="%ENTITYITEMUNLOCALIZEDNAME%"),
				sublime.CompletionItem(trigger="ENTITYITEMCOUNT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Amount of the dropped item", completion="%ENTITYITEMCOUNT%"),
				sublime.CompletionItem(trigger="ENTITYITEMDISPLAYNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Displayname of the dropped item", completion="%ENTITYITEMDISPLAYNAME%"),
				sublime.CompletionItem(trigger="ENTITYITEMDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Damage of the dropped item", completion="%ENTITYITEMDAMAGE%"),
				sublime.CompletionItem(trigger="ENTITYITEMMAXDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Max damage of the dropped item", completion="%ENTITYITEMMAXDAMAGE%"),
				sublime.CompletionItem(trigger="ENTITYITEMMETADATA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Metadata of the dropped item", completion="%ENTITYITEMMETADATA%"),
				sublime.CompletionItem(trigger="ENTITYITEMENCHANTED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="True if the dropped item is enchanted", completion="%ENTITYITEMENCHANTED%"),
				sublime.CompletionItem(trigger="ENTITYITEMSTACKABLE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="True if the dropped item is stackable", completion="%ENTITYITEMSTACKABLE%"),
				sublime.CompletionItem(trigger="ENTITYMAINHANDNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Name of the mainhand item", completion="%ENTITYMAINHANDNAME%"),
				sublime.CompletionItem(trigger="ENTITYMAINHANDID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="ID of the mainhand item", completion="%ENTITYMAINHANDID%"),
				sublime.CompletionItem(trigger="ENTITYMAINHANDNID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Numerical ID of the mainhand item", completion="%ENTITYMAINHANDNID%"),
				sublime.CompletionItem(trigger="ENTITYMAINHANDDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Damage of the mainhand item", completion="%ENTITYMAINHANDDAMAGE%"),
				sublime.CompletionItem(trigger="ENTITYMAINHANDCOUNT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Amount of the mainhand item", completion="%ENTITYMAINHANDCOUNT%"),
				sublime.CompletionItem(trigger="ENTITYMAINHANDENCHANTMENTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Enchantments of the mainhand item", completion="%ENTITYMAINHANDENCHANTMENTS%"),
				sublime.CompletionItem(trigger="ENTITYOFFHANDNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Name of the offhand item", completion="%ENTITYOFFHANDNAME%"),
				sublime.CompletionItem(trigger="ENTITYOFFHANDID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="ID of the offhand item", completion="%ENTITYOFFHANDID%"),
				sublime.CompletionItem(trigger="ENTITYOFFHANDNID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Numerical ID of the offhand item", completion="%ENTITYOFFHANDNID%"),
				sublime.CompletionItem(trigger="ENTITYOFFHANDDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Damage of the offhand item", completion="%ENTITYOFFHANDDAMAGE%"),
				sublime.CompletionItem(trigger="ENTITYOFFHANDCOUNT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Amount of the offhand item", completion="%ENTITYOFFHANDCOUNT%"),
				sublime.CompletionItem(trigger="ENTITYOFFHANDENCHANTMENTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Enchantments of the offhand item", completion="%ENTITYOFFHANDENCHANTMENTS%"),
				sublime.CompletionItem(trigger="ENTITYBOOTSNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Name of the boots item", completion="%ENTITYBOOTSNAME%"),
				sublime.CompletionItem(trigger="ENTITYBOOTSID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="ID of the boots item", completion="%ENTITYBOOTSID%"),
				sublime.CompletionItem(trigger="ENTITYBOOTSNID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Numerical ID of the boots item", completion="%ENTITYBOOTSNID%"),
				sublime.CompletionItem(trigger="ENTITYBOOTSDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Damage of the boots item", completion="%ENTITYBOOTSDAMAGE%"),
				sublime.CompletionItem(trigger="ENTITYBOOTSCOUNT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Amount of the boots item", completion="%ENTITYBOOTSCOUNT%"),
				sublime.CompletionItem(trigger="ENTITYBOOTSENCHANTMENTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Enchantments of the boots item", completion="%ENTITYBOOTSENCHANTMENTS%"),
				sublime.CompletionItem(trigger="ENTITYLEGGINGSNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Name of the leggings item", completion="%ENTITYLEGGINGSNAME%"),
				sublime.CompletionItem(trigger="ENTITYLEGGINGSID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="ID of the leggings item", completion="%ENTITYLEGGINGSID%"),
				sublime.CompletionItem(trigger="ENTITYLEGGINGSNID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Numerical ID of the leggings item", completion="%ENTITYLEGGINGSNID%"),
				sublime.CompletionItem(trigger="ENTITYLEGGINGSDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Damage of the leggings item", completion="%ENTITYLEGGINGSDAMAGE%"),
				sublime.CompletionItem(trigger="ENTITYLEGGINGSCOUNT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Amount of the leggings item", completion="%ENTITYLEGGINGSCOUNT%"),
				sublime.CompletionItem(trigger="ENTITYLEGGINGSENCHANTMENTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Enchantments of the leggings item", completion="%ENTITYLEGGINGSENCHANTMENTS%"),
				sublime.CompletionItem(trigger="ENTITYCHESTPLATENAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Name of the chestplate item", completion="%ENTITYCHESTPLATENAME%"),
				sublime.CompletionItem(trigger="ENTITYCHESTPLATEID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="ID of the chestplate item", completion="%ENTITYCHESTPLATEID%"),
				sublime.CompletionItem(trigger="ENTITYCHESTPLATENID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Numerical ID of the chestplate item", completion="%ENTITYCHESTPLATENID%"),
				sublime.CompletionItem(trigger="ENTITYCHESTPLATEDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Damage of the chestplate item", completion="%ENTITYCHESTPLATEDAMAGE%"),
				sublime.CompletionItem(trigger="ENTITYCHESTPLATECOUNT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Amount of the chestplate item", completion="%ENTITYCHESTPLATECOUNT%"),
				sublime.CompletionItem(trigger="ENTITYCHESTPLATEENCHANTMENTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Enchantments of the chestplate item", completion="%ENTITYCHESTPLATEENCHANTMENTS%"),
				sublime.CompletionItem(trigger="ENTITYHELMETNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Name of the helmet item", completion="%ENTITYHELMETNAME%"),
				sublime.CompletionItem(trigger="ENTITYHELMETID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="ID of the helmet item", completion="%ENTITYHELMETID%"),
				sublime.CompletionItem(trigger="ENTITYHELMETNID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Numerical ID of the helmet item", completion="%ENTITYHELMETNID%"),
				sublime.CompletionItem(trigger="ENTITYHELMETDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Damage of the helmet item", completion="%ENTITYHELMETDAMAGE%"),
				sublime.CompletionItem(trigger="ENTITYHELMETCOUNT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Amount of the helmet item", completion="%ENTITYHELMETCOUNT%"),
				sublime.CompletionItem(trigger="ENTITYHELMETENCHANTMENTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Enchantments of the helmet item", completion="%ENTITYHELMETENCHANTMENTS%"),
				sublime.CompletionItem(trigger="EHITX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="X value of entity your're looking at or 0 if not looking at an entity", completion="%EHITX%"),
				sublime.CompletionItem(trigger="EHITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Y value of entity your're looking at or 0 if not looking at an entity", completion="%EHITY%"),
				sublime.CompletionItem(trigger="EHITZ", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Entities Iterator Module)", details="Z value of entity your're looking at or 0 if not looking at an entity", completion="%EHITZ%"),
				sublime.CompletionItem(trigger="FARHIT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(FarHit Module)", details="Extended reach %HIT%", completion="%FARHIT%"),
				sublime.CompletionItem(trigger="FARHITID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(FarHit Module)", details="Extended reach %HITID%", completion="%FARHITID%"),
				sublime.CompletionItem(trigger="FARHITDATA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(FarHit Module)", details="Extended reach %HITDATA%", completion="%FARHITDATA%"),
				sublime.CompletionItem(trigger="FARHITNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(FarHit Module)", details="Extended reach %HITNAME%", completion="%FARHITNAME%"),
				sublime.CompletionItem(trigger="FARHITSIDE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(FarHit Module)", details="Extended reach %HITSIDE%", completion="%FARHITSIDE%"),
				sublime.CompletionItem(trigger="FARHITX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(FarHit Module)", details="Extended reach %HITX%", completion="%FARHITX%"),
				sublime.CompletionItem(trigger="FARHITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(FarHit Module)", details="Extended reach %HITY%", completion="%FARHITY%"),
				sublime.CompletionItem(trigger="FARHITZ", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(FarHit Module)", details="Extended reach %HITZ%", completion="%FARHITZ%"),
				sublime.CompletionItem(trigger="FARHITUUID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(FarHit Module)", details="Extended reach %HITUUID%", completion="%FARHITUUID%"),
				sublime.CompletionItem(trigger="FARHITDIST", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(FarHit Module)", details="Extended reach %HITDIST%", completion="%FARHITDIST%"),
				sublime.CompletionItem(trigger="MODULEFARHIT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(FarHit Module)", details="Returns true if the module is installed", completion="%MODULEFARHIT%"),
				sublime.CompletionItem(trigger="FUNCTION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="(Functions Module)", details="Define a function", completion="FUNCTION ${1:<name>}(${2:[parameter], ...});\n\t$3\nENDFUNCTION;$4"),
				sublime.CompletionItem(trigger="RETURN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Functions Module)", details="Returns a value inside of a function", completion="RETURN(${1:<value>});"),
				sublime.CompletionItem(trigger="RETURN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Functions Module)", details="Returns a value inside of a function", completion="RETURN ${1:<value>};"),
				sublime.CompletionItem(trigger="CALL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Functions Module)", details="Alternative way of calling functions", completion="CALL(${1:<name>},${2:[parameter], ...});"),
				sublime.CompletionItem(trigger="GETSLOTITEMEXT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(GetSlotItemExtended Module)", details="+ Argument for the itemname of item", completion="${2:&${1:[itemid]} = }getslotitemext(#${3:<slotid>},&${1:[itemid]},${4:[stacksize]},${5:[damage]},${6:[itemname]});"),
				sublime.CompletionItem(trigger="GETSLOTITEMNBT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(GetSlotItemExtended Module)", details="+ Argument for the nbt of item", completion="${2:&${1:[itemid]} = }getslotitemnbt(#${3:<slotid>},${1:[itemid]},${4:[stacksize]},${5:[damage]},${6:[nbt]});"),
				sublime.CompletionItem(trigger="GETSLOTITEMENCHANTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(GetSlotItemExtended Module)", details="+ Argument for enchantments", completion="${2:&${1:[itemid]} = }getslotitemenchants(#${3:<slotid>},${1:[itemid]},${4:[stacksize]},${5:[damage]},${6:[enchants]});"),
				sublime.CompletionItem(trigger="HTTPGET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(HTTP Module)", details="Httpget request to url", completion="${2:&${1:[response]}[] = }httpget(${3:<url>},${4:<query>},#${5:<status>},&${1:[response]});"),
				sublime.CompletionItem(trigger="HTTPPOST", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(HTTP Module)", details="Httppost request to url with data", completion="${2:&${1:[response]}[] = }httppost(${3:<url>},${4:<data>},#${5:<status>},&${1:[response]});"),
				sublime.CompletionItem(trigger="HTTPPUT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(HTTP Module)", details="Httpput request to url with data", completion="${2:&${1:[response]}[] = }httpput(${3:<url>},${4:<data>},#${5:<status>},&${1:[response]});"),
				sublime.CompletionItem(trigger="HTTPDELETE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(HTTP Module)", details="Request to specified url", completion="${2:&${1:[response]}[] = }httpdelete(${3:<url>},${4:<query>},#${5:<status>},&${1:[response]});"),
				sublime.CompletionItem(trigger="URLENCODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(HTTP Module)", details="Url encodes the string", completion="${2:&${1:[output]} = }urlencode(${3:<string>},&${1:[output]});"),
				sublime.CompletionItem(trigger="SETREQUESTHEADER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(HTTP Module)", details="Sets header for next request", completion="SETREQUESTHEADER(&${1:<field>},&${2:<value>});"),
				sublime.CompletionItem(trigger="MODULEHTTP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(HTTP Module)", details="Returns true if the module is installed", completion="%MODULEHTTP%"),
				sublime.CompletionItem(trigger="ISBOOLEAN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Checks if the value is a boolean", completion="${2:[${1:bool}] = }isboolean(${3:<string>},${1:[bool]});"),
				sublime.CompletionItem(trigger="ISFLOAT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Checks if the value is a float", completion="${2:${1:[bool]} = }isfloat(${3:<string>},${1:[bool]});"),
				sublime.CompletionItem(trigger="ISINTEGER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Checks if the value is an integer", completion="${2:${1:[bool]} = }isinteger(${3:<string>},${1:[bool]});"),
				sublime.CompletionItem(trigger="ISJSONARRAY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Checks if the value is a json array", completion="${2:${1:[bool]} = }isjsonarray(${3:<string>},${1:[bool]});"),
				sublime.CompletionItem(trigger="ISJSONOBJECT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Checks if the value is a json object", completion="${2:${1:[bool]} = }isjsonobject(${3:<string>},${1:[bool]});"),
				sublime.CompletionItem(trigger="ISJSONPRIMITIVE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Checks if value isjson primitive", completion="${2:${1:[bool]} = }isjsonprimitive(${3:<string>}${1:,[bool}]);"),
				sublime.CompletionItem(trigger="ISNUMBER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Checks if the value is a number", completion="${2:${1:[bool]} = }isnumber(${3:<string>},${1:[bool]});"),
				sublime.CompletionItem(trigger="ISSTRING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Checks if the value is a string", completion="${2:${1:[bool]} = }isstring(${3:<string>},${1:[bool]});"),
				sublime.CompletionItem(trigger="JSONADD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Adds key and value to the json", completion="${2:&${1:[output]} = }jsonadd(${3:<json>},${4:<key>},${5:<value>},&${1:[output]});"),
				sublime.CompletionItem(trigger="JSONGET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Gets value of a key", completion="${2:&${1:[output]} = }jsonget(${3:<json>},${4:<key>},&${1:[output]});"),
				sublime.CompletionItem(trigger="JSONHAS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Returns if the json contains the key", completion="${2:${1:[bool]} = }jsonhas(${3:<json>},${4:<key>},${1:[bool]});"),
				sublime.CompletionItem(trigger="JSONREMOVE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Removes a key-value-pair from the json", completion="${2:&${1:[output]} = }jsonremove(${3:<json>},${4:<key>},&${1:[output]});"),
				sublime.CompletionItem(trigger="GETJSONKEYS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Returns list of all keys of the json", completion="${2:&${1:[keys]} = }getjsonkeys(${3:<json>},&${1:[keys]}[]);"),
				sublime.CompletionItem(trigger="GETJSONARRAY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Returns json as key:value array", completion="${2:&${1:[array]} = }getjsonasarray(${3:<json>},${1:[array]}[]));"),
				sublime.CompletionItem(trigger="JSONARRAYADD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Adds an element to the json array", completion="${2:&${1:[jsonarray]} = }jsonarrayadd(${3:<jsonarray>},${4:<element>},&${1:[jsonarray]});"),
				sublime.CompletionItem(trigger="JSONARRAYGET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Returns the element of the jsonarray", completion="${2:&${1:[output]} = }jsonarrayget(${3:<jsonarray>},${4:<index>},&${1:[output]});"),
				sublime.CompletionItem(trigger="JSONARRAYSIZE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(JSON Module)", details="Returns the size of the jsonarray", completion="${2:#${1:[size]} = }jsonarraysize(${3:<jsonarray>},#${1:[size]});"),
				sublime.CompletionItem(trigger="MODULEJSON", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(JSON Module)", details="Returns true if the module is installed", completion="%MODULEJSON%"),
				sublime.CompletionItem(trigger="CALCYAWTO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="+ Y argument for pitch", completion="CALCYAWTO(${1:<xpos>},${2:<ypos>},${3:<zpos>},#${4:[yaw]},#${5:[dist]},#${6:[pitch]});"),
				sublime.CompletionItem(trigger="GETSLOTITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="+ Nbt argument", completion="GETSLOTITEM(${1:<slotid>},&${2:<itemid>},#${3:[stacksize]},#${4:[datavar]},&${5:[nbt]});"),
				sublime.CompletionItem(trigger="HTTP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Creates a http request", completion="&${1:response} = http(${2:[get|post|put|delete]},${3:<url>},${4:[output stream]},${5:[headers]});"),
				sublime.CompletionItem(trigger="IFFILEEXISTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="(Klacaiba Module)", details="Executes if the file exists at &#60;path&#62;", completion="IFFILEEXISTS(${1:<path>},${2:[expression]});\n	$3\nENDIF;\n$4"),
				sublime.CompletionItem(trigger="MKDIR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Creates directory", completion="MKDIR(${1:<path>});"),
				sublime.CompletionItem(trigger="WRITEFILE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Writes array to file", completion="WRITEFILE(${1:<path>},&${2:<writefile>}[],${3:[append]});"),
				sublime.CompletionItem(trigger="GETJSONASARRAY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Returns json as key:value array", completion="&${1:array}[] = getjsonasarray(${2:<json>},${3:[format]});"),
				sublime.CompletionItem(trigger="GETJSONKEYS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Retuns list of the keys of json", completion="&${1:keys}[] = getjsonkeys(${2:<json>});"),
				sublime.CompletionItem(trigger="JSONGET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Retuns object of key of specified json", completion="&${1:object} = jsonget(${2:<json>},${3:<key>});"),
				sublime.CompletionItem(trigger="SORT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Sorts the arrays synchronously", completion="SORT(${1:[asc,dsc]},${2:<array>}[],${3:[array]}[]);"),
				sublime.CompletionItem(trigger="TEAMMEMBERS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Lists scoreboard team members", completion="&${1:<members/teams>}[] = teammembers(${2:[team]});"),
				sublime.CompletionItem(trigger="SCORE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Returns score of player in objective", completion="<${1:&score|&scores[]|&obectives[]}> = score(${2:[objectivename]},${3:[playername]});"),
				sublime.CompletionItem(trigger="COUNTDOWNTO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Countdown to the specified datetime", completion="COUNTDOWNTO(${1:<until>});"),
				sublime.CompletionItem(trigger="COUNTDOWNFROM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Countdown from the specified time", completion="COUNTDOWNFROM(${1:<start>});"),
				sublime.CompletionItem(trigger="COUNTUP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Creates a countup from the current time", completion="COUNTUP();"),
				sublime.CompletionItem(trigger="COUNTER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Current value of the countdown or countup", completion="COUNTER(${1:<id>});"),
				sublime.CompletionItem(trigger="SECTOTIME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Formats the amount of seconds to time", completion="&${1:time} = sectotime(${2:<seconds>},${3:[format]});"),
				sublime.CompletionItem(trigger="GETCHESTNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Returns the name of the open chest", completion="&${1:name} = getchestname();"),
				sublime.CompletionItem(trigger="GETEMPTYSLOTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Returns empty slots in inventory", completion="#${1:slots} = getemptyslots(${2:[include non full slots]});"),
				sublime.CompletionItem(trigger="GETMOUSEITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Gets info about the held item", completion="${2:&${1:[id]} = }getmouseitem(&${1:[id]},#${3:[stacksizevar]},#${4:[datavar]},&${5:[nbt]});"),
				sublime.CompletionItem(trigger="GETSLOTITEMINV", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Gets information about the item in the specified slot", completion="${2:[&${1:<id>}] = }getslotiteminv(${3:<slotid>},&${1:<id>},#${4:[stacksizevar]},#${5:[datavar]},&${6:[nbt]});"),
				sublime.CompletionItem(trigger="GETSLOTINV", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Gets slot containing item in inventory", completion="#${1:[slot]} = getslotinv(${2:<item>}:${3:[damage]},#${4:<idvar>},${5:[startfromslotid]});"),
				sublime.CompletionItem(trigger="IFINVISFULL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="(Klacaiba Module)", details="Executes if the inventory is full", completion="IFINVISFULL(${1:[item]});\n	$2\nENDIF;\n$3"),
				sublime.CompletionItem(trigger="IFININV", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="(Klacaiba Module)", details="Executes if the &#60;items&#62; are in the inventory, mode can be 'any', 'all' or number", completion="IFININV(${1:[mode]},${2:<items>});\n	$3\nENDIF;\n$4"),
				sublime.CompletionItem(trigger="IFENCHANTED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="(Klacaiba Module)", details="Executes if the item at &#60;slot&#62; is enchanted", completion="IFENCHANTED(${1:<slot>},&${2:[item]},#${3:[stacksize]},#${4:[datavar]},&${5:[nbt]});\n	$6\nENDIF;\n$7"),
				sublime.CompletionItem(trigger="SETSLOTITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Set the contents of a hotbar slot", completion="SETSLOTITEM(${1:<item>}:${2:[damage]}${3:,<slot>},${4:[amount]},${5:[nbt]});"),
				sublime.CompletionItem(trigger="GETFISHHOOK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Get the x, y and z (3dp) of the bobber", completion="${2:#${1:[ytotal]} = }getfishhook(#${3:[x]},#${4:[xprecision]},#${5:[y]},#${6:[yprecision]},#${7:[z]},#${8:[zprecision]});"),
				sublime.CompletionItem(trigger="MAP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Maps the value x from minfrom-maxfrom to minto-maxto", completion="#${1:result} = map(${2:<x>},${3:<minfrom>},${4:<maxfrom>},${5:<minto>},${6:<maxto>});"),
				sublime.CompletionItem(trigger="PARTICLE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Spawns particles similar to the vanilla command", completion="${2:&${1:errors}[] = }particle(${3:<particlename>},${4:<x>},${5:<y>},${6:<z>},${7:<dx>},${8:<dy>},${9:<dz>},${10:[count]},${11:[mode]});"),
				sublime.CompletionItem(trigger="COUNTITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Amount of items in your current inventory", completion="#${1:count} = countitem(${2:<item>}:${3:[damage]});"),
				sublime.CompletionItem(trigger="COUNTITEMINV", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Amount of items in your survival inventory", completion="#${1:count} = countiteminv(${2:<item>}:${3:[damage]});"),
				sublime.CompletionItem(trigger="CREATECONTROL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Creates a control on the specified screen at row and column position", completion="${2:[&${1:controlname}] = }createcontrol(${3:<screenname|layouts|types>},${4:[element type]},${5:[row]},${6:[column]});"),
				sublime.CompletionItem(trigger="DELETECONTROL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Deletes a control by name from any gui", completion="DELETECONTROL(${1:<controlname>});"),
				sublime.CompletionItem(trigger="TIMESTAMPTODATE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Format a timestamp in seconds", completion="&${1:date} = timestamptodate(${2:<timestamp>},${3:[in milliseconds|date format]},${4:[in milliseconds]});"),
				sublime.CompletionItem(trigger="STOP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Stops macro matching regex or array", completion="STOP(${1:[array|regex]});"),
				sublime.CompletionItem(trigger="STRLEN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Returns the length of the string or 0 if none is present", completion="#${1:length} = strlen(${2:<string>});"),
				sublime.CompletionItem(trigger="GETBREAKSPEED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Returns the amount of time required to break a block or 0 if infinite of none specified", completion="#${1:ticks} = getbreakspeed(${2:<blockid>});"),
				sublime.CompletionItem(trigger="IFCANHARVESTBLOCK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="(Klacaiba Module)", details="Executes if the &#60;blockid&#62; can currently be harvested", completion="IFCANHARVESTBLOCK(${1:<blockid>});\n	$2\nENDIF;\n$3"),
				sublime.CompletionItem(trigger="POLLEVENT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="(Klacaiba Module)", details="Opens a stack with an infinite iterator for a specific event", completion="POLLEVENT(${1:[event]});\n	$3\n	AWAIT;\nNEXT;\n$4"),
				sublime.CompletionItem(trigger="POLLALL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module)", details="List all variables of the event", completion="%POLLALL%"),
				sublime.CompletionItem(trigger="AWAIT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Should be placed above the closing next of a pollevent", completion="AWAIT;"),
				sublime.CompletionItem(trigger="LATENCY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module)", details="Ping of the player to the server", completion="%LATENCY%"),
				sublime.CompletionItem(trigger="HACKED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module)", details="Whether all the functions of the module have been applied to the client", completion="%HACKED%"),
				sublime.CompletionItem(trigger="MINECRAFTDIR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module)", details="Filepath of the current minecraft directory", completion="%MINECRAFTDIR%"),
				sublime.CompletionItem(trigger="MACROSCONFIGDIR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module)", details="%MINECRAFTDIR%/.liteconfig/common/macros", completion="%MACROSCONFIGDIR%"),
				sublime.CompletionItem(trigger="FILESEPERATOR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module)", details="Default path seperator used by the system", completion="%FILESEPERATOR%"),
				sublime.CompletionItem(trigger="KLACAIBAVERSION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module)", details="Returns the version of klacaiba", completion="%KLACAIBAVERSION%"),
				sublime.CompletionItem(trigger="TEAMS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Iterates over all teams", completion="TEAMS"),
				sublime.CompletionItem(trigger="OBJECTIVES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Iterates over all objectives", completion="OBJECTIVES"),
				sublime.CompletionItem(trigger="SCORE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Iterates over all scores", completion="SCORE"),
				sublime.CompletionItem(trigger="ACTIONS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Iterates over all actions", completion="ACTIONS"),
				sublime.CompletionItem(trigger="EVENTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Iterates over all events", completion="EVENTS"),
				sublime.CompletionItem(trigger="INVENTORY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Iterates over your inventory", completion="INVENTORY"),
				sublime.CompletionItem(trigger="PLAYERUUID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - players iterator)", details="UUID of the player with dashes", completion="%PLAYERUUID%"),
				sublime.CompletionItem(trigger="PLAYERDISPLAYNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - players iterator)", details="Displayname of the player", completion="%PLAYERDISPLAYNAME%"),
				sublime.CompletionItem(trigger="PLAYERTEAM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - players iterator)", details="Scoreboard team of the player as JSON", completion="%PLAYERTEAM%"),
				sublime.CompletionItem(trigger="PLAYERPING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - players iterator)", details="Ping of the player", completion="%PLAYERPING%"),
				sublime.CompletionItem(trigger="PLAYERISLEGACY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - players iterator)", details="Whether the player uses a legacy account", completion="%PLAYERISLEGACY%"),
				sublime.CompletionItem(trigger="TEAMALLOWFRIENDLYFIRE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - teams iterator)", details="If the team allows friendly fire", completion="%TEAMALLOWFRIENDLYFIRE%"),
				sublime.CompletionItem(trigger="TEAMCOLLISIONRULE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - teams iterator)", details="Collisionrule of the team", completion="%TEAMCOLLISIONRULE%"),
				sublime.CompletionItem(trigger="TEAMCOLOR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - teams iterator)", details="Color of the team", completion="%TEAMCOLOR%"),
				sublime.CompletionItem(trigger="TEAMDEATHMESSAGEVISIBILITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - teams iterator)", details="Deathmessage visibility ruleing of the team", completion="%TEAMDEATHMESSAGEVISIBILITY%"),
				sublime.CompletionItem(trigger="TEAMDISPLAYNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - teams iterator)", details="Displayname of the team", completion="%TEAMDISPLAYNAME%"),
				sublime.CompletionItem(trigger="TEAMNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - teams iterator)", details="Name of the team", completion="%TEAMNAME%"),
				sublime.CompletionItem(trigger="TEAMNAMETAGVISIBILITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - teams iterator)", details="Nametag visibility of the team", completion="%TEAMNAMETAGVISIBILITY%"),
				sublime.CompletionItem(trigger="TEAMSEEFRIENDLYINVISIBLES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - teams iterator)", details="Whether the team can see friendly invisibles", completion="%TEAMSEEFRIENDLYINVISIBLES%"),
				sublime.CompletionItem(trigger="TEAMPREFIX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - teams iterator)", details="Prefix of the team", completion="%TEAMPREFIX%"),
				sublime.CompletionItem(trigger="TEAMSUFFIX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - teams iterator)", details="Suffix of the team", completion="%TEAMSUFFIX%"),
				sublime.CompletionItem(trigger="TEAMMEMBERS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - teams iterator)", details="Membernames of the team", completion="%TEAMMEMBERS%"),
				sublime.CompletionItem(trigger="OBJECTIVECRITERIA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - objectives iterator)", details="Criteria of the objective", completion="%OBJECTIVECRITERIA%"),
				sublime.CompletionItem(trigger="OBJECTIVEDISPLAYNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - objectives iterator)", details="Displayname of the objective", completion="%OBJECTIVEDISPLAYNAME%"),
				sublime.CompletionItem(trigger="OBJECTIVENAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - objectives iterator)", details="Name of the objective", completion="%OBJECTIVENAME%"),
				sublime.CompletionItem(trigger="OBJECTIVERENDERTYPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - objectives iterator)", details="Rendertype of the objective", completion="%OBJECTIVERENDERTYPE%"),
				sublime.CompletionItem(trigger="SCOREOBJECTIVENAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - scores iterator)", details="Name of the associated objective", completion="%SCOREOBJECTIVENAME%"),
				sublime.CompletionItem(trigger="SCOREPLAYERNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - scores iterator)", details="Name of the owning player", completion="%SCOREPLAYERNAME%"),
				sublime.CompletionItem(trigger="SCOREVALUE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - scores iterator)", details="Value of the score", completion="%SCOREVALUE%"),
				sublime.CompletionItem(trigger="TRADES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Klacaiba Module)", details="Iterates over all trades", completion="TRADES"),
				sublime.CompletionItem(trigger="TRADEBUYITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - trades iterator)", completion="%TRADEBUYITEM%"),
				sublime.CompletionItem(trigger="TRADEBUYITEMAMOUNT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - trades iterator)", completion="%TRADEBUYITEMAMOUNT%"),
				sublime.CompletionItem(trigger="TRADEBUYITEM2", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - trades iterator)", completion="%TRADEBUYITEM2%"),
				sublime.CompletionItem(trigger="TRADEBUYITEM2AMOUNT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - trades iterator)", completion="%TRADEBUYITEM2AMOUNT%"),
				sublime.CompletionItem(trigger="TRADESELLITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - trades iterator)", completion="%TRADESELLITEM%"),
				sublime.CompletionItem(trigger="TRADESELLITEMAMOUNT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - trades iterator)", completion="%TRADESELLITEMAMOUNT%"),
				sublime.CompletionItem(trigger="TRADEUSES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - trades iterator)", completion="%TRADEUSES%"),
				sublime.CompletionItem(trigger="TRADEMAXUSES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - trades iterator)", completion="%TRADEMAXUSES%"),
				sublime.CompletionItem(trigger="SLOTINDEX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - inventory iterator)", details="current index of slot", completion="%SLOTINDEX%"),
				sublime.CompletionItem(trigger="SLOTID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - inventory iterator)", details="current id of slot", completion="%SLOTID%"),
				sublime.CompletionItem(trigger="SLOTSTACKSIZE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - inventory iterator)", details="current stacksize of slot", completion="%SLOTSTACKSIZE%"),
				sublime.CompletionItem(trigger="SLOTDATAVAR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - inventory iterator)", details="current datavar of slot", completion="%SLOTDATAVAR%"),
				sublime.CompletionItem(trigger="SLOTTAG", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - inventory iterator)", details="current tag of slot", completion="%SLOTTAG%"),
				sublime.CompletionItem(trigger="SOUNDXPOSF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="XPOS of sound as float", completion="%SOUNDXPOSF%"),
				sublime.CompletionItem(trigger="SOUNDYPOSF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="YPOS of sound as float", completion="%SOUNDYPOSF%"),
				sublime.CompletionItem(trigger="SOUNDZPOSF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="ZPOS of sound as float", completion="%SOUNDZPOSF%"),
				sublime.CompletionItem(trigger="SOUNDXPOS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="XPOS of sound as int", completion="%SOUNDXPOS%"),
				sublime.CompletionItem(trigger="SOUNDYPOS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="YPOS of sound as int", completion="%SOUNDYPOS%"),
				sublime.CompletionItem(trigger="SOUNDZPOS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="ZPOS of sound as int", completion="%SOUNDZPOS%"),
				sublime.CompletionItem(trigger="SOUNDCANREPEAT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="Whether the sound is able to repeat", completion="%SOUNDCANREPEAT%"),
				sublime.CompletionItem(trigger="SOUNDATTENUATIONTYPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="Type of attenuation", completion="%SOUNDATTENUATIONTYPE%"),
				sublime.CompletionItem(trigger="SOUNDCATEGORY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="Category of sound", completion="%SOUNDCATEGORY%"),
				sublime.CompletionItem(trigger="SOUNDPITCH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="Pitch of the sound as float", completion="%SOUNDPITCH%"),
				sublime.CompletionItem(trigger="SOUNDVOLUME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="Volume of the sound as float", completion="%SOUNDVOLUME%"),
				sublime.CompletionItem(trigger="SOUNDRESOURCE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Klacaiba Module - onSound event)", details="Resourcepath of the sound", completion="%SOUNDRESOURCE%"),
				sublime.CompletionItem(trigger="GETSLOTNBT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Macro Modules Essential)", details="Get nbt of item in slot", completion="GETSLOTNBT(${1:<slotid>},${2:<path>},&${3:[itemId]},#${4:[stackSize]},#${5:[damage]});"),
				sublime.CompletionItem(trigger="PRESSBUTTON", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Macro Modules Essential)", details="Press button", completion="PRESSBUTTON(${1:<buttonid>},${2:[button]});"),
				sublime.CompletionItem(trigger="GETPROP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Macro Modules Essential)", details="gets property of block at coordinates", completion="GETPROP(${1:<x>},${2:<y>},${3:<z>},${4:<propname>},#${5:[propvar]});"),
				sublime.CompletionItem(trigger="SLOTMIDDLECLICK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Macro Modules Essential)", details="middle click inventory slot", completion="SLOTMIDDLECLICK(${1:<slotid>});"),
				sublime.CompletionItem(trigger="RECONNECT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Reconnect Module)", details="Auto reconnects to a server", completion="RECONNECT(${1:<on|off|10-300>});"),
				sublime.CompletionItem(trigger="RECONNECT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Reconnect Module)", details="Whether or not auto reconnect is enabled", completion="%RECONNECT%"),
				sublime.CompletionItem(trigger="GETDENSITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(scaneUtils Module)", details="Searches for sugarcane in the given direction", completion="GETDENSITY(${1:[N/E/S/W]},#${2:<limit_search>},&${3:<initial_position>},#${4:<blocks_searched>},#${5:<sugarcane_found>});"),
				sublime.CompletionItem(trigger="GETITEMSTACKSIZE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(scaneUtils Module)", details="Searches the inventory, returns the stacksize", completion="#${1:stacksize} = getitemstacksize(&${2:<item_name>},#${3:[limit_search]});"),
				sublime.CompletionItem(trigger="GETPERCENTAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(scaneUtils Module)", details="Does first divided by second times 100", completion="GETPERCENTAGE(#${1:[percentage]},#${2:<first>},#${3:<second>});"),
				sublime.CompletionItem(trigger="GETSLOTPOSITIONS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(scaneUtils Module)", details="Searches the inventory, returns the position", completion="GETSLOTPOSITIONS(&${1:<item_name>},#${2:<result_position>},#${3:[result_stacksize]});"),
				sublime.CompletionItem(trigger="GETHITSIGNTEXT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(SignText Module)", details="Returns signtext of hit sign", completion="${2:&${1:[outarray]}[] = }gethitsigntext(&${1:[outarray]}[]);"),
				sublime.CompletionItem(trigger="GETSIGNTEXT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(SignText Module)", details="Returns signtext at coordinates", completion="${2:&${1:[outarray]} = }getsigntext(${3:<x>},${4:<y>},${5:<z>},&${1:[outarray]});"),
				sublime.CompletionItem(trigger="SETSIGNTEXT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(SignText Module)", details="Set text of sign in SP", completion="SETSIGNTEXT(${1:<x>},${2:<y>}${3:,<z>},${4:<line1>},${5:<line2>},${6:<line3>},${7:<line4>});"),
				sublime.CompletionItem(trigger="MODULESIGNTEXT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(SignText Module)", details="Returns true if the module is installed", completion="%MODULESIGNTEXT%"),
				sublime.CompletionItem(trigger="SWITCH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_SNIPPET, annotation="SWITCH…CASE…DEFAULT…ENDCASE (Switch Case Module)", details="Switch case statement", completion="SWITCH(${1:<expression>});\n	CASE(${2:<value>});\n		$3\n	DEFAULT;\n		$4\nENDSWITCH;\n$5"),
				sublime.CompletionItem(trigger="CASE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Switch Case Module)", details="case statement", completion="CASE(${1:<value>});\n	$2"),
				sublime.CompletionItem(trigger="EVAL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Utilities Module)", details="Evaluates an expression", completion="${2:&${1:[result]} = }eval(&${1:[result]},${3:<expression string>});"),
				sublime.CompletionItem(trigger="CHAR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Utilities Module)", details="Puts set unicode value into &char", completion="CHAR(&${1:<char>},${2:<decimal unicode value>});"),
				sublime.CompletionItem(trigger="MOD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Utilities Module)", details="Evaluates num1 modulo num2", completion="MOD(#${1:<result>},${2:<num1>},${3:<num2>});"),
				sublime.CompletionItem(trigger="OLDNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Utilities Module)", details="Gets the past names of a user", completion="OLDNAME(&${1:<names>}[],${2:<username>});"),
				sublime.CompletionItem(trigger="READFILE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Utilities Module)", details="Gets the content of a file", completion="READFILE(&${1:<content>}[],${2:<filename>});"),
				sublime.CompletionItem(trigger="READFILE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Utilities Module)", details="Reads file from path", completion="${2:&${1:<content>}[] = }readfile(&${1:[content]}[],${3:<path>});"),
				sublime.CompletionItem(trigger="UNIX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Utilities Module)", details="Gets the s/ms of current timestamp", completion="${2:#${1:[seconds]} = }unix(#${1:[seconds]},#${3:[milliseconds]});"),
				sublime.CompletionItem(trigger="TRIM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Utils Module)", details="Removes whitespace", completion="&${1:result} = trim(&${2:string});"),
				sublime.CompletionItem(trigger="SHUFFLE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Utils Module)", details="Shuffles an array", completion="SHUFFLE(${1:array[]});"),
				sublime.CompletionItem(trigger="ACTIONNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - actions iterator)", details="Action name", completion="%ACTIONNAME%"),
				sublime.CompletionItem(trigger="ACTIONUSAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - actions iterator)", details="Action usage", completion="%ACTIONUSAGE%"),
				sublime.CompletionItem(trigger="ACTIONRETURN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - actions iterator)", details="Action return", completion="%ACTIONRETURN%"),
				sublime.CompletionItem(trigger="ACTIONDESCRIPTION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - actions iterator)", details="Action description", completion="%ACTIONDESCRIPTION%"),
				sublime.CompletionItem(trigger="EVENTNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - events iterator)", details="Event name", completion="%EVENTNAME%"),
				sublime.CompletionItem(trigger="EVENTID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - events iterator)", details="Event id", completion="%EVENTID%"),
				sublime.CompletionItem(trigger="EVENTHELP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - events iterator)", details="Event help", completion="%EVENTHELP%"),
				sublime.CompletionItem(trigger="ITERATORS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Utils Module - iterators iterator)", details="Iterates over all iterators", completion="ITERATORS"),
				sublime.CompletionItem(trigger="ITERATORNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - iterators iterator)", details="Iterator name", completion="%ITERATORNAME%"),
				sublime.CompletionItem(trigger="NEWEFFECT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - onPotionEffect event)", details="New potion effect", completion="%NEWEFFECT%"),
				sublime.CompletionItem(trigger="NEWEFFECTID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - onPotionEffect event)", details="New potion effect id", completion="%NEWEFFECTID%"),
				sublime.CompletionItem(trigger="NEWEFFECTNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - onPotionEffect event)", details="New potion effect name", completion="%NEWEFFECTNAME%"),
				sublime.CompletionItem(trigger="NEWEFFECTPOWER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - onPotionEffect event)", details="New potion effect power", completion="%NEWEFFECTPOWER%"),
				sublime.CompletionItem(trigger="NEWEFFECTTIME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Utils Module - onPotionEffect event)", details="New potion effect time", completion="%NEWEFFECTTIME%"),
				sublime.CompletionItem(trigger="NOTIFY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(WindowsNotification Module)", details="Creates a system tray", completion="NOTIFY(${1:[title]},${2:[message]});"),
				sublime.CompletionItem(trigger="MOD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Yaku's Module)", details="Modulus function", completion="MOD(#${1:<divident>},#${2:<divisor>});"),
				sublime.CompletionItem(trigger="TRUNC", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Yaku's Module)", details="Returns the integer part of the number", completion="TRUNC(#${1:<float>});"),
				sublime.CompletionItem(trigger="ACKERMANN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Yaku's Module)", details="Ackermann function implementation", completion="ACKERMANN(#${1:<m>},#${2:<n>});"),
				sublime.CompletionItem(trigger="CALCSTACKS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Yaku's Module)", details="Calculates stacks", completion="CALCSTACKS(#${1:<items>},#${2:[stacks]},#${3:[leftovers]});"),
				sublime.CompletionItem(trigger="PICKMOD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Yaku's Module)", details="Improved original pick action", completion="PICKMOD(${1:[namespace]}:${2:<itemid>}:${3:[damage]},${4:[addInCreative]});"),
				sublime.CompletionItem(trigger="ANTIGHOST", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(Yaku's Module)", details="Resolve ghost blocks issue", completion="ANTIGHOST;"),
				sublime.CompletionItem(trigger="ALT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%ALT%"),
				sublime.CompletionItem(trigger="ALT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~ALT%"),
				sublime.CompletionItem(trigger="CTRL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%CTRL%"),
				sublime.CompletionItem(trigger="CTRL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~CTRL%"),
				sublime.CompletionItem(trigger="KEY_0", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_0%"),
				sublime.CompletionItem(trigger="KEY_0", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_0%"),
				sublime.CompletionItem(trigger="KEY_1", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_1%"),
				sublime.CompletionItem(trigger="KEY_1", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_1%"),
				sublime.CompletionItem(trigger="KEY_2", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_2%"),
				sublime.CompletionItem(trigger="KEY_2", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_2%"),
				sublime.CompletionItem(trigger="KEY_3", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_3%"),
				sublime.CompletionItem(trigger="KEY_3", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_3%"),
				sublime.CompletionItem(trigger="KEY_4", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_4%"),
				sublime.CompletionItem(trigger="KEY_4", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_4%"),
				sublime.CompletionItem(trigger="KEY_5", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_5%"),
				sublime.CompletionItem(trigger="KEY_5", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_5%"),
				sublime.CompletionItem(trigger="KEY_6", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_6%"),
				sublime.CompletionItem(trigger="KEY_6", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_6%"),
				sublime.CompletionItem(trigger="KEY_7", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_7%"),
				sublime.CompletionItem(trigger="KEY_7", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_7%"),
				sublime.CompletionItem(trigger="KEY_8", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_8%"),
				sublime.CompletionItem(trigger="KEY_8", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_8%"),
				sublime.CompletionItem(trigger="KEY_9", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_9%"),
				sublime.CompletionItem(trigger="KEY_9", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_9%"),
				sublime.CompletionItem(trigger="KEY_A", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_A%"),
				sublime.CompletionItem(trigger="KEY_A", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_A%"),
				sublime.CompletionItem(trigger="KEY_ADD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_ADD%"),
				sublime.CompletionItem(trigger="KEY_ADD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_ADD%"),
				sublime.CompletionItem(trigger="KEY_APOSTROPHE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_APOSTROPHE%"),
				sublime.CompletionItem(trigger="KEY_APOSTROPHE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_APOSTROPHE%"),
				sublime.CompletionItem(trigger="KEY_APPS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_APPS%"),
				sublime.CompletionItem(trigger="KEY_APPS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_APPS%"),
				sublime.CompletionItem(trigger="KEY_AT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_AT%"),
				sublime.CompletionItem(trigger="KEY_AT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_AT%"),
				sublime.CompletionItem(trigger="KEY_AX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_AX%"),
				sublime.CompletionItem(trigger="KEY_AX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_AX%"),
				sublime.CompletionItem(trigger="KEY_B", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_B%"),
				sublime.CompletionItem(trigger="KEY_B", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_B%"),
				sublime.CompletionItem(trigger="KEY_BACK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_BACK%"),
				sublime.CompletionItem(trigger="KEY_BACK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_BACK%"),
				sublime.CompletionItem(trigger="KEY_BACKSLASH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_BACKSLASH%"),
				sublime.CompletionItem(trigger="KEY_BACKSLASH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_BACKSLASH%"),
				sublime.CompletionItem(trigger="KEY_C", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_C%"),
				sublime.CompletionItem(trigger="KEY_C", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_C%"),
				sublime.CompletionItem(trigger="KEY_CAPITAL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_CAPITAL%"),
				sublime.CompletionItem(trigger="KEY_CAPITAL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_CAPITAL%"),
				sublime.CompletionItem(trigger="KEY_CIRCUMFLEX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_CIRCUMFLEX%"),
				sublime.CompletionItem(trigger="KEY_CIRCUMFLEX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_CIRCUMFLEX%"),
				sublime.CompletionItem(trigger="KEY_CLEAR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_CLEAR%"),
				sublime.CompletionItem(trigger="KEY_CLEAR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_CLEAR%"),
				sublime.CompletionItem(trigger="KEY_COLON", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_COLON%"),
				sublime.CompletionItem(trigger="KEY_COLON", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_COLON%"),
				sublime.CompletionItem(trigger="KEY_COMMA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_COMMA%"),
				sublime.CompletionItem(trigger="KEY_COMMA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_COMMA%"),
				sublime.CompletionItem(trigger="KEY_CONVERT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_CONVERT%"),
				sublime.CompletionItem(trigger="KEY_CONVERT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_CONVERT%"),
				sublime.CompletionItem(trigger="KEY_D", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_D%"),
				sublime.CompletionItem(trigger="KEY_D", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_D%"),
				sublime.CompletionItem(trigger="KEY_DECIMAL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_DECIMAL%"),
				sublime.CompletionItem(trigger="KEY_DECIMAL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_DECIMAL%"),
				sublime.CompletionItem(trigger="KEY_DELETE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_DELETE%"),
				sublime.CompletionItem(trigger="KEY_DELETE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_DELETE%"),
				sublime.CompletionItem(trigger="KEY_DIVIDE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_DIVIDE%"),
				sublime.CompletionItem(trigger="KEY_DIVIDE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_DIVIDE%"),
				sublime.CompletionItem(trigger="KEY_DOWN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_DOWN%"),
				sublime.CompletionItem(trigger="KEY_DOWN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_DOWN%"),
				sublime.CompletionItem(trigger="KEY_E", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_E%"),
				sublime.CompletionItem(trigger="KEY_E", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_E%"),
				sublime.CompletionItem(trigger="KEY_END", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_END%"),
				sublime.CompletionItem(trigger="KEY_END", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_END%"),
				sublime.CompletionItem(trigger="KEY_EQUALS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_EQUALS%"),
				sublime.CompletionItem(trigger="KEY_EQUALS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_EQUALS%"),
				sublime.CompletionItem(trigger="KEY_ESCAPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_ESCAPE%"),
				sublime.CompletionItem(trigger="KEY_ESCAPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_ESCAPE%"),
				sublime.CompletionItem(trigger="KEY_F", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F%"),
				sublime.CompletionItem(trigger="KEY_F", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F%"),
				sublime.CompletionItem(trigger="KEY_F1", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F1%"),
				sublime.CompletionItem(trigger="KEY_F1", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F1%"),
				sublime.CompletionItem(trigger="KEY_F10", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F10%"),
				sublime.CompletionItem(trigger="KEY_F10", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F10%"),
				sublime.CompletionItem(trigger="KEY_F11", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F11%"),
				sublime.CompletionItem(trigger="KEY_F11", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F11%"),
				sublime.CompletionItem(trigger="KEY_F12", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F12%"),
				sublime.CompletionItem(trigger="KEY_F12", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F12%"),
				sublime.CompletionItem(trigger="KEY_F13", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F13%"),
				sublime.CompletionItem(trigger="KEY_F13", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F13%"),
				sublime.CompletionItem(trigger="KEY_F14", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F14%"),
				sublime.CompletionItem(trigger="KEY_F14", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F14%"),
				sublime.CompletionItem(trigger="KEY_F15", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F15%"),
				sublime.CompletionItem(trigger="KEY_F15", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F15%"),
				sublime.CompletionItem(trigger="KEY_F16", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F16%"),
				sublime.CompletionItem(trigger="KEY_F16", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F16%"),
				sublime.CompletionItem(trigger="KEY_F17", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F17%"),
				sublime.CompletionItem(trigger="KEY_F17", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F17%"),
				sublime.CompletionItem(trigger="KEY_F18", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F18%"),
				sublime.CompletionItem(trigger="KEY_F18", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F18%"),
				sublime.CompletionItem(trigger="KEY_F19", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F19%"),
				sublime.CompletionItem(trigger="KEY_F19", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F19%"),
				sublime.CompletionItem(trigger="KEY_F2", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F2%"),
				sublime.CompletionItem(trigger="KEY_F2", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F2%"),
				sublime.CompletionItem(trigger="KEY_F3", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F3%"),
				sublime.CompletionItem(trigger="KEY_F3", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F3%"),
				sublime.CompletionItem(trigger="KEY_F4", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F4%"),
				sublime.CompletionItem(trigger="KEY_F4", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F4%"),
				sublime.CompletionItem(trigger="KEY_F5", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F5%"),
				sublime.CompletionItem(trigger="KEY_F5", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F5%"),
				sublime.CompletionItem(trigger="KEY_F6", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F6%"),
				sublime.CompletionItem(trigger="KEY_F6", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F6%"),
				sublime.CompletionItem(trigger="KEY_F7", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F7%"),
				sublime.CompletionItem(trigger="KEY_F7", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F7%"),
				sublime.CompletionItem(trigger="KEY_F8", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F8%"),
				sublime.CompletionItem(trigger="KEY_F8", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F8%"),
				sublime.CompletionItem(trigger="KEY_F9", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_F9%"),
				sublime.CompletionItem(trigger="KEY_F9", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_F9%"),
				sublime.CompletionItem(trigger="KEY_FUNCTION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_FUNCTION%"),
				sublime.CompletionItem(trigger="KEY_FUNCTION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_FUNCTION%"),
				sublime.CompletionItem(trigger="KEY_G", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_G%"),
				sublime.CompletionItem(trigger="KEY_G", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_G%"),
				sublime.CompletionItem(trigger="KEY_GRAVE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_GRAVE%"),
				sublime.CompletionItem(trigger="KEY_GRAVE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_GRAVE%"),
				sublime.CompletionItem(trigger="KEY_H", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_H%"),
				sublime.CompletionItem(trigger="KEY_H", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_H%"),
				sublime.CompletionItem(trigger="KEY_HOME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_HOME%"),
				sublime.CompletionItem(trigger="KEY_HOME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_HOME%"),
				sublime.CompletionItem(trigger="KEY_I", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_I%"),
				sublime.CompletionItem(trigger="KEY_I", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_I%"),
				sublime.CompletionItem(trigger="KEY_INSERT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_INSERT%"),
				sublime.CompletionItem(trigger="KEY_INSERT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_INSERT%"),
				sublime.CompletionItem(trigger="KEY_J", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_J%"),
				sublime.CompletionItem(trigger="KEY_J", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_J%"),
				sublime.CompletionItem(trigger="KEY_K", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_K%"),
				sublime.CompletionItem(trigger="KEY_K", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_K%"),
				sublime.CompletionItem(trigger="KEY_KANA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_KANA%"),
				sublime.CompletionItem(trigger="KEY_KANA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_KANA%"),
				sublime.CompletionItem(trigger="KEY_KANJI", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_KANJI%"),
				sublime.CompletionItem(trigger="KEY_KANJI", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_KANJI%"),
				sublime.CompletionItem(trigger="KEY_L", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_L%"),
				sublime.CompletionItem(trigger="KEY_L", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_L%"),
				sublime.CompletionItem(trigger="KEY_LBRACKET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_LBRACKET%"),
				sublime.CompletionItem(trigger="KEY_LBRACKET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_LBRACKET%"),
				sublime.CompletionItem(trigger="KEY_LCONTROL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_LCONTROL%"),
				sublime.CompletionItem(trigger="KEY_LCONTROL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_LCONTROL%"),
				sublime.CompletionItem(trigger="KEY_LEFT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_LEFT%"),
				sublime.CompletionItem(trigger="KEY_LEFT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_LEFT%"),
				sublime.CompletionItem(trigger="KEY_LMENU", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_LMENU%"),
				sublime.CompletionItem(trigger="KEY_LMENU", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_LMENU%"),
				sublime.CompletionItem(trigger="KEY_LMETA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_LMETA%"),
				sublime.CompletionItem(trigger="KEY_LMETA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_LMETA%"),
				sublime.CompletionItem(trigger="KEY_LSHIFT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_LSHIFT%"),
				sublime.CompletionItem(trigger="KEY_LSHIFT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_LSHIFT%"),
				sublime.CompletionItem(trigger="KEY_M", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_M%"),
				sublime.CompletionItem(trigger="KEY_M", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_M%"),
				sublime.CompletionItem(trigger="KEY_MINUS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_MINUS%"),
				sublime.CompletionItem(trigger="KEY_MINUS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_MINUS%"),
				sublime.CompletionItem(trigger="KEY_MOUSE3", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_MOUSE3%"),
				sublime.CompletionItem(trigger="KEY_MOUSE3", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_MOUSE3%"),
				sublime.CompletionItem(trigger="KEY_MOUSE4", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_MOUSE4%"),
				sublime.CompletionItem(trigger="KEY_MOUSE4", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_MOUSE4%"),
				sublime.CompletionItem(trigger="KEY_MULTIPLY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_MULTIPLY%"),
				sublime.CompletionItem(trigger="KEY_MULTIPLY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_MULTIPLY%"),
				sublime.CompletionItem(trigger="KEY_N", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_N%"),
				sublime.CompletionItem(trigger="KEY_N", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_N%"),
				sublime.CompletionItem(trigger="KEY_NEXT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NEXT%"),
				sublime.CompletionItem(trigger="KEY_NEXT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NEXT%"),
				sublime.CompletionItem(trigger="KEY_NOCONVERT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NOCONVERT%"),
				sublime.CompletionItem(trigger="KEY_NOCONVERT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NOCONVERT%"),
				sublime.CompletionItem(trigger="KEY_NONE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NONE%"),
				sublime.CompletionItem(trigger="KEY_NONE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NONE%"),
				sublime.CompletionItem(trigger="KEY_NUMLOCK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMLOCK%"),
				sublime.CompletionItem(trigger="KEY_NUMLOCK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMLOCK%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD0", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPAD0%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD0", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPAD0%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD1", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPAD1%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD1", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPAD1%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD2", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPAD2%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD2", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPAD2%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD3", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPAD3%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD3", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPAD3%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD4", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPAD4%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD4", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPAD4%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD5", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPAD5%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD5", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPAD5%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD6", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPAD6%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD6", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPAD6%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD7", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPAD7%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD7", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPAD7%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD8", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPAD8%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD8", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPAD8%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD9", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPAD9%"),
				sublime.CompletionItem(trigger="KEY_NUMPAD9", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPAD9%"),
				sublime.CompletionItem(trigger="KEY_NUMPADCOMMA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPADCOMMA%"),
				sublime.CompletionItem(trigger="KEY_NUMPADCOMMA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPADCOMMA%"),
				sublime.CompletionItem(trigger="KEY_NUMPADENTER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPADENTER%"),
				sublime.CompletionItem(trigger="KEY_NUMPADENTER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPADENTER%"),
				sublime.CompletionItem(trigger="KEY_NUMPADEQUALS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_NUMPADEQUALS%"),
				sublime.CompletionItem(trigger="KEY_NUMPADEQUALS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_NUMPADEQUALS%"),
				sublime.CompletionItem(trigger="KEY_O", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_O%"),
				sublime.CompletionItem(trigger="KEY_O", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_O%"),
				sublime.CompletionItem(trigger="KEY_P", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_P%"),
				sublime.CompletionItem(trigger="KEY_P", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_P%"),
				sublime.CompletionItem(trigger="KEY_PAUSE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_PAUSE%"),
				sublime.CompletionItem(trigger="KEY_PAUSE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_PAUSE%"),
				sublime.CompletionItem(trigger="KEY_PERIOD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_PERIOD%"),
				sublime.CompletionItem(trigger="KEY_PERIOD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_PERIOD%"),
				sublime.CompletionItem(trigger="KEY_POWER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_POWER%"),
				sublime.CompletionItem(trigger="KEY_POWER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_POWER%"),
				sublime.CompletionItem(trigger="KEY_PRIOR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_PRIOR%"),
				sublime.CompletionItem(trigger="KEY_PRIOR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_PRIOR%"),
				sublime.CompletionItem(trigger="KEY_Q", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_Q%"),
				sublime.CompletionItem(trigger="KEY_Q", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_Q%"),
				sublime.CompletionItem(trigger="KEY_R", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_R%"),
				sublime.CompletionItem(trigger="KEY_R", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_R%"),
				sublime.CompletionItem(trigger="KEY_RBRACKET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_RBRACKET%"),
				sublime.CompletionItem(trigger="KEY_RBRACKET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_RBRACKET%"),
				sublime.CompletionItem(trigger="KEY_RCONTROL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_RCONTROL%"),
				sublime.CompletionItem(trigger="KEY_RCONTROL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_RCONTROL%"),
				sublime.CompletionItem(trigger="KEY_RETURN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_RETURN%"),
				sublime.CompletionItem(trigger="KEY_RETURN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_RETURN%"),
				sublime.CompletionItem(trigger="KEY_RIGHT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_RIGHT%"),
				sublime.CompletionItem(trigger="KEY_RIGHT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_RIGHT%"),
				sublime.CompletionItem(trigger="KEY_RMENU", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_RMENU%"),
				sublime.CompletionItem(trigger="KEY_RMENU", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_RMENU%"),
				sublime.CompletionItem(trigger="KEY_RMETA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_RMETA%"),
				sublime.CompletionItem(trigger="KEY_RMETA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_RMETA%"),
				sublime.CompletionItem(trigger="KEY_RSHIFT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_RSHIFT%"),
				sublime.CompletionItem(trigger="KEY_RSHIFT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_RSHIFT%"),
				sublime.CompletionItem(trigger="KEY_S", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_S%"),
				sublime.CompletionItem(trigger="KEY_S", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_S%"),
				sublime.CompletionItem(trigger="KEY_SCROLL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_SCROLL%"),
				sublime.CompletionItem(trigger="KEY_SCROLL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_SCROLL%"),
				sublime.CompletionItem(trigger="KEY_SECTION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_SECTION%"),
				sublime.CompletionItem(trigger="KEY_SECTION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_SECTION%"),
				sublime.CompletionItem(trigger="KEY_SEMICOLON", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_SEMICOLON%"),
				sublime.CompletionItem(trigger="KEY_SEMICOLON", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_SEMICOLON%"),
				sublime.CompletionItem(trigger="KEY_SLASH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_SLASH%"),
				sublime.CompletionItem(trigger="KEY_SLASH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_SLASH%"),
				sublime.CompletionItem(trigger="KEY_SLEEP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_SLEEP%"),
				sublime.CompletionItem(trigger="KEY_SLEEP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_SLEEP%"),
				sublime.CompletionItem(trigger="KEY_SPACE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_SPACE%"),
				sublime.CompletionItem(trigger="KEY_SPACE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_SPACE%"),
				sublime.CompletionItem(trigger="KEY_STOP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_STOP%"),
				sublime.CompletionItem(trigger="KEY_STOP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_STOP%"),
				sublime.CompletionItem(trigger="KEY_SUBTRACT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_SUBTRACT%"),
				sublime.CompletionItem(trigger="KEY_SUBTRACT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_SUBTRACT%"),
				sublime.CompletionItem(trigger="KEY_SYSRQ", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_SYSRQ%"),
				sublime.CompletionItem(trigger="KEY_SYSRQ", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_SYSRQ%"),
				sublime.CompletionItem(trigger="KEY_T", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_T%"),
				sublime.CompletionItem(trigger="KEY_T", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_T%"),
				sublime.CompletionItem(trigger="KEY_TAB", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_TAB%"),
				sublime.CompletionItem(trigger="KEY_TAB", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_TAB%"),
				sublime.CompletionItem(trigger="KEY_U", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_U%"),
				sublime.CompletionItem(trigger="KEY_U", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_U%"),
				sublime.CompletionItem(trigger="KEY_UNDERLINE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_UNDERLINE%"),
				sublime.CompletionItem(trigger="KEY_UNDERLINE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_UNDERLINE%"),
				sublime.CompletionItem(trigger="KEY_UNLABELED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_UNLABELED%"),
				sublime.CompletionItem(trigger="KEY_UNLABELED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_UNLABELED%"),
				sublime.CompletionItem(trigger="KEY_UP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_UP%"),
				sublime.CompletionItem(trigger="KEY_UP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_UP%"),
				sublime.CompletionItem(trigger="KEY_V", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_V%"),
				sublime.CompletionItem(trigger="KEY_V", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_V%"),
				sublime.CompletionItem(trigger="KEY_W", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_W%"),
				sublime.CompletionItem(trigger="KEY_W", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_W%"),
				sublime.CompletionItem(trigger="KEY_X", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_X%"),
				sublime.CompletionItem(trigger="KEY_X", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_X%"),
				sublime.CompletionItem(trigger="KEY_Y", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_Y%"),
				sublime.CompletionItem(trigger="KEY_Y", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_Y%"),
				sublime.CompletionItem(trigger="KEY_YEN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_YEN%"),
				sublime.CompletionItem(trigger="KEY_YEN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_YEN%"),
				sublime.CompletionItem(trigger="KEY_Z", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%KEY_Z%"),
				sublime.CompletionItem(trigger="KEY_Z", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~KEY_Z%"),
				sublime.CompletionItem(trigger="LMOUSE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%LMOUSE%"),
				sublime.CompletionItem(trigger="LMOUSE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~LMOUSE%"),
				sublime.CompletionItem(trigger="MIDDLEMOUSE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%MIDDLEMOUSE%"),
				sublime.CompletionItem(trigger="MIDDLEMOUSE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~MIDDLEMOUSE%"),
				sublime.CompletionItem(trigger="RMOUSE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%RMOUSE%"),
				sublime.CompletionItem(trigger="RMOUSE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~RMOUSE%"),
				sublime.CompletionItem(trigger="SHIFT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%SHIFT%"),
				sublime.CompletionItem(trigger="SHIFT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(Pressed at start)", completion="%~SHIFT%"),
				sublime.CompletionItem(trigger="HIT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Type of the thing the Player is looking at", completion="%HIT%"),
				sublime.CompletionItem(trigger="HIT_AGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_AGE%"),
				sublime.CompletionItem(trigger="HIT_ATTACHED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_ATTACHED%"),
				sublime.CompletionItem(trigger="HIT_AXIS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_AXIS%"),
				sublime.CompletionItem(trigger="HIT_BITES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_BITES%"),
				sublime.CompletionItem(trigger="HIT_CHECK_DECAY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_CHECK_DECAY%"),
				sublime.CompletionItem(trigger="HIT_COLOR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_COLOR%"),
				sublime.CompletionItem(trigger="HIT_CONDITIONAL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_CONDITIONAL%"),
				sublime.CompletionItem(trigger="HIT_CONTENTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_CONTENTS%"),
				sublime.CompletionItem(trigger="HIT_DAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_DAMAGE%"),
				sublime.CompletionItem(trigger="HIT_DECAYABLE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_DECAYABLE%"),
				sublime.CompletionItem(trigger="HIT_DELAY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_DELAY%"),
				sublime.CompletionItem(trigger="HIT_DISARMED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_DISARMED%"),
				sublime.CompletionItem(trigger="HIT_DOWN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_DOWN%"),
				sublime.CompletionItem(trigger="HIT_EAST", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_EAST%"),
				sublime.CompletionItem(trigger="HIT_ENABLED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_ENABLED%"),
				sublime.CompletionItem(trigger="HIT_EXPLODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_EXPLODE%"),
				sublime.CompletionItem(trigger="HIT_EXTENDED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_EXTENDED%"),
				sublime.CompletionItem(trigger="HIT_EYE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_EYE%"),
				sublime.CompletionItem(trigger="HIT_FACING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_FACING%"),
				sublime.CompletionItem(trigger="HIT_HALF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_HALF%"),
				sublime.CompletionItem(trigger="HIT_HAS_BOTTLE_0", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_HAS_BOTTLE_0%"),
				sublime.CompletionItem(trigger="HIT_HAS_BOTTLE_1", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_HAS_BOTTLE_1%"),
				sublime.CompletionItem(trigger="HIT_HAS_BOTTLE_2", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_HAS_BOTTLE_2%"),
				sublime.CompletionItem(trigger="HIT_HAS_RECORD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_HAS_RECORD%"),
				sublime.CompletionItem(trigger="HIT_HINGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_HINGE%"),
				sublime.CompletionItem(trigger="HIT_IN_WALL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_IN_WALL%"),
				sublime.CompletionItem(trigger="HIT_LAYERS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_LAYERS%"),
				sublime.CompletionItem(trigger="HIT_LEGACY_DATA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_LEGACY_DATA%"),
				sublime.CompletionItem(trigger="HIT_LEVEL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_LEVEL%"),
				sublime.CompletionItem(trigger="HIT_LOCKED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_LOCKED%"),
				sublime.CompletionItem(trigger="HIT_MODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_MODE%"),
				sublime.CompletionItem(trigger="HIT_MOISTURE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_MOISTURE%"),
				sublime.CompletionItem(trigger="HIT_NODROP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_NODROP%"),
				sublime.CompletionItem(trigger="HIT_NORTH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_NORTH%"),
				sublime.CompletionItem(trigger="HIT_OCCUPIED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_OCCUPIED%"),
				sublime.CompletionItem(trigger="HIT_OPEN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_OPEN%"),
				sublime.CompletionItem(trigger="HIT_PART", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_PART%"),
				sublime.CompletionItem(trigger="HIT_POWER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_POWER%"),
				sublime.CompletionItem(trigger="HIT_POWERED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_POWERED%"),
				sublime.CompletionItem(trigger="HIT_ROTATION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_ROTATION%"),
				sublime.CompletionItem(trigger="HIT_SEAMLESS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_SEAMLESS%"),
				sublime.CompletionItem(trigger="HIT_SHAPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_SHAPE%"),
				sublime.CompletionItem(trigger="HIT_SHORT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_SHORT%"),
				sublime.CompletionItem(trigger="HIT_SNOWY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_SNOWY%"),
				sublime.CompletionItem(trigger="HIT_SOUTH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_SOUTH%"),
				sublime.CompletionItem(trigger="HIT_STAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_STAGE%"),
				sublime.CompletionItem(trigger="HIT_TRIGGERED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_TRIGGERED%"),
				sublime.CompletionItem(trigger="HIT_TYPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_TYPE%"),
				sublime.CompletionItem(trigger="HIT_UP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_UP%"),
				sublime.CompletionItem(trigger="HIT_VARIANT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_VARIANT%"),
				sublime.CompletionItem(trigger="HIT_WEST", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_WEST%"),
				sublime.CompletionItem(trigger="HIT_WET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%HIT_WET%"),
				sublime.CompletionItem(trigger="HITDATA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Metadata of the thing the Player is looking at", completion="%HITDATA%"),
				sublime.CompletionItem(trigger="HITID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="ID of the thing the Player is looking at", completion="%HITID%"),
				sublime.CompletionItem(trigger="HITNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Displayname of the thing the Player is looking at", completion="%HITNAME%"),
				sublime.CompletionItem(trigger="HITPROGRESS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Block breaking progress of the block the Player is looking at", completion="%HITPROGRESS%"),
				sublime.CompletionItem(trigger="HITSIDE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Block side of the block the Player is looking at", completion="%HITSIDE%"),
				sublime.CompletionItem(trigger="HITUUID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="UUID of the looked at entity or player", completion="%HITUUID%"),
				sublime.CompletionItem(trigger="HITX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="X position of the block the Player is looking at", completion="%HITX%"),
				sublime.CompletionItem(trigger="HITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Y position of the block the Player is looking at", completion="%HITY%"),
				sublime.CompletionItem(trigger="HITZ", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Z position of the block the Player is looking at", completion="%HITZ%"),
				sublime.CompletionItem(trigger="TRACE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Performs a ray trace operation which sets the raytrace variables in the local scope", completion="TRACE(${1:<distance>},${2:[entities]});"),
				sublime.CompletionItem(trigger="TRACE_AGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_AGE%"),
				sublime.CompletionItem(trigger="TRACE_ATTACHED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_ATTACHED%"),
				sublime.CompletionItem(trigger="TRACE_AXIS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_AXIS%"),
				sublime.CompletionItem(trigger="TRACE_BITES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_BITES%"),
				sublime.CompletionItem(trigger="TRACE_CHECK_DECAY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_CHECK_DECAY%"),
				sublime.CompletionItem(trigger="TRACE_COLOR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_COLOR%"),
				sublime.CompletionItem(trigger="TRACE_CONDITIONAL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_CONDITIONAL%"),
				sublime.CompletionItem(trigger="TRACE_CONTENTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_CONTENTS%"),
				sublime.CompletionItem(trigger="TRACE_DAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_DAMAGE%"),
				sublime.CompletionItem(trigger="TRACE_DECAYABLE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_DECAYABLE%"),
				sublime.CompletionItem(trigger="TRACE_DELAY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_DELAY%"),
				sublime.CompletionItem(trigger="TRACE_DISARMED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_DISARMED%"),
				sublime.CompletionItem(trigger="TRACE_DOWN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_DOWN%"),
				sublime.CompletionItem(trigger="TRACE_EAST", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_EAST%"),
				sublime.CompletionItem(trigger="TRACE_ENABLED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_ENABLED%"),
				sublime.CompletionItem(trigger="TRACE_EXPLODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_EXPLODE%"),
				sublime.CompletionItem(trigger="TRACE_EXTENDED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_EXTENDED%"),
				sublime.CompletionItem(trigger="TRACE_EYE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_EYE%"),
				sublime.CompletionItem(trigger="TRACE_FACING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_FACING%"),
				sublime.CompletionItem(trigger="TRACE_HALF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_HALF%"),
				sublime.CompletionItem(trigger="TRACE_HAS_BOTTLE_0", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_HAS_BOTTLE_0%"),
				sublime.CompletionItem(trigger="TRACE_HAS_BOTTLE_1", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_HAS_BOTTLE_1%"),
				sublime.CompletionItem(trigger="TRACE_HAS_BOTTLE_2", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_HAS_BOTTLE_2%"),
				sublime.CompletionItem(trigger="TRACE_HAS_RECORD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_HAS_RECORD%"),
				sublime.CompletionItem(trigger="TRACE_HINGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_HINGE%"),
				sublime.CompletionItem(trigger="TRACE_IN_WALL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_IN_WALL%"),
				sublime.CompletionItem(trigger="TRACE_LAYERS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_LAYERS%"),
				sublime.CompletionItem(trigger="TRACE_LEGACY_DATA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_LEGACY_DATA%"),
				sublime.CompletionItem(trigger="TRACE_LEVEL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_LEVEL%"),
				sublime.CompletionItem(trigger="TRACE_LOCKED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_LOCKED%"),
				sublime.CompletionItem(trigger="TRACE_MODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_MODE%"),
				sublime.CompletionItem(trigger="TRACE_MOISTURE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_MOISTURE%"),
				sublime.CompletionItem(trigger="TRACE_NODROP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_NODROP%"),
				sublime.CompletionItem(trigger="TRACE_NORTH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_NORTH%"),
				sublime.CompletionItem(trigger="TRACE_OCCUPIED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_OCCUPIED%"),
				sublime.CompletionItem(trigger="TRACE_OPEN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_OPEN%"),
				sublime.CompletionItem(trigger="TRACE_PART", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_PART%"),
				sublime.CompletionItem(trigger="TRACE_POWER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_POWER%"),
				sublime.CompletionItem(trigger="TRACE_POWERED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_POWERED%"),
				sublime.CompletionItem(trigger="TRACE_ROTATION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_ROTATION%"),
				sublime.CompletionItem(trigger="TRACE_SEAMLESS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_SEAMLESS%"),
				sublime.CompletionItem(trigger="TRACE_SHAPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_SHAPE%"),
				sublime.CompletionItem(trigger="TRACE_SHORT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_SHORT%"),
				sublime.CompletionItem(trigger="TRACE_SNOWY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_SNOWY%"),
				sublime.CompletionItem(trigger="TRACE_SOUTH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_SOUTH%"),
				sublime.CompletionItem(trigger="TRACE_STAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_STAGE%"),
				sublime.CompletionItem(trigger="TRACE_TRIGGERED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_TRIGGERED%"),
				sublime.CompletionItem(trigger="TRACE_TYPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_TYPE%"),
				sublime.CompletionItem(trigger="TRACE_UP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_UP%"),
				sublime.CompletionItem(trigger="TRACE_VARIANT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_VARIANT%"),
				sublime.CompletionItem(trigger="TRACE_WEST", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_WEST%"),
				sublime.CompletionItem(trigger="TRACE_WET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, completion="%TRACE_WET%"),
				sublime.CompletionItem(trigger="TRACEDATA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Metadata of the block", completion="%TRACEDATA%"),
				sublime.CompletionItem(trigger="TRACEID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="The id", completion="%TRACEID%"),
				sublime.CompletionItem(trigger="TRACENAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="The name", completion="%TRACENAME%"),
				sublime.CompletionItem(trigger="TRACESIDE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Side of the block", completion="%TRACESIDE%"),
				sublime.CompletionItem(trigger="TRACETYPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="The type of the result", completion="%TRACETYPE%"),
				sublime.CompletionItem(trigger="TRACEUUID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Returns the UUID of other players", completion="%TRACEUUID%"),
				sublime.CompletionItem(trigger="TRACEX", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="X position", completion="%TRACEX%"),
				sublime.CompletionItem(trigger="TRACEY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Y position", completion="%TRACEY%"),
				sublime.CompletionItem(trigger="TRACEZ", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Z position", completion="%TRACEZ%"),
				sublime.CompletionItem(trigger="ACHIEVEMENTGET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Displays a popup you get when completing an advancement with a custom message and optionally a custom item", completion="ACHIEVEMENTGET(${1:<text>},${2:[itemid]}:${3:[damage]});"),
				sublime.CompletionItem(trigger="AMBIENTVOLUME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Volume level for Ambient/Environment", completion="%AMBIENTVOLUME%"),
				sublime.CompletionItem(trigger="ARMOUR", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Armour points (each icon equals 2 points)", completion="%ARMOUR%"),
				sublime.CompletionItem(trigger="ARRAYSIZE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Stores the size of the specified array in #outvar", completion="ARRAYSIZE(${1:<array>}[],#${2:[outvar]});"),
				sublime.CompletionItem(trigger="ASSIGN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Internal function", completion="<VAR> = <value>;"),
				sublime.CompletionItem(trigger="ATTACKPOWER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Attack power", completion="%ATTACKPOWER%"),
				sublime.CompletionItem(trigger="ATTACKSPEED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Attack speed", completion="%ATTACKSPEED%"),
				sublime.CompletionItem(trigger="BIND", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Set the specified key binding to the specified key code", completion="BIND(${1:<bind>},${2:<keycode>});"),
				sublime.CompletionItem(trigger="BINDGUI", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Binds the specified custom screen to the slot specified", completion="BINDGUI(${1:<slot>},${2:<screen>});"),
				sublime.CompletionItem(trigger="BIOME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Biome the Player is currently in", completion="%BIOME%"),
				sublime.CompletionItem(trigger="BLOCKVOLUME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Volume level for Blocks", completion="%BLOCKVOLUME%"),
				sublime.CompletionItem(trigger="BOOTSDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Maximum uses of the Players boots", completion="%BOOTSDAMAGE%"),
				sublime.CompletionItem(trigger="BOOTSDURABILITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Durability of the Players boots", completion="%BOOTSDURABILITY%"),
				sublime.CompletionItem(trigger="BOOTSID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="ID of the Players boots", completion="%BOOTSID%"),
				sublime.CompletionItem(trigger="BOOTSNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Displayname of the Players boots", completion="%BOOTSNAME%"),
				sublime.CompletionItem(trigger="BOWCHARGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Charge of bow", completion="%BOWCHARGE%"),
				sublime.CompletionItem(trigger="BREAK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Interrupts exection of the innermost loop", completion="BREAK;"),
				sublime.CompletionItem(trigger="CALCYAWTO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Calculates the absolute yaw angle", completion="CALCYAWTO(${1:<xpos>},${2:<zpos>},#${3:[yaw]},#${4:[dist}ance]);"),
				sublime.CompletionItem(trigger="CAMERA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Set the current camera mode, call with no arguments to toggle modes", completion="CAMERA(${1:[mode]});"),
				sublime.CompletionItem(trigger="CAMERA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Current camera mode", completion="%CAMERA%"),
				sublime.CompletionItem(trigger="CANFLY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Whether the Player can fly", completion="%CANFLY%"),
				sublime.CompletionItem(trigger="CARDINALYAW", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Yaw of the player relative to north (YAW + 180)", completion="%CARDINALYAW%"),
				sublime.CompletionItem(trigger="CHAT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onChat) Chat message with control codes", completion="%CHAT%"),
				sublime.CompletionItem(trigger="CHATCLEAN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onChat) Chat message without control codes", completion="%CHATCLEAN%"),
				sublime.CompletionItem(trigger="CHATFILTER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Enable or disable the chat filter", completion="CHATFILTER(${1:<enabled>});"),
				sublime.CompletionItem(trigger="CHATHEIGHT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Set height of the Minecraft chat whilst ingame", completion="CHATHEIGHT(${1:<value>},${2:[time]});"),
				sublime.CompletionItem(trigger="CHATHEIGHTFOCUSED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Set height of the Minecraft chat whilst in the chat GUI", completion="CHATHEIGHTFOCUSED(${1:<value>},${2:[time]});"),
				sublime.CompletionItem(trigger="CHATJSON", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onBetterChat) Chat message in JSON", completion="%CHATMESSAGE%"),
				sublime.CompletionItem(trigger="CHATMESSAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onChat) The message part of an incoming chat line, could be wrong", completion="%CHATMESSAGE%"),
				sublime.CompletionItem(trigger="CHATOPACITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Set opacity of the Minecraft chat", completion="CHATOPACITY(${1:<value>},${2:[time]});"),
				sublime.CompletionItem(trigger="CHATPLAYER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onChat) The player who send a chat line, could be wrong", completion="%CHATPLAYER%"),
				sublime.CompletionItem(trigger="CHATSCALE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Set scale of the Minecraft chat", completion="CHATSCALE(${1:<value>},${2:[time]});"),
				sublime.CompletionItem(trigger="CHATVISIBLE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Set visibility of minecraft chat", completion="CHATVISIBLE(${1:<value>});"),
				sublime.CompletionItem(trigger="CHATWIDTH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Set width of the Minecraft chat", completion="CHATWIDTH(${1:<value}>,${2:[time]});"),
				sublime.CompletionItem(trigger="CHESTPLATEDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Maximum uses of the Players chestplate", completion="%CHESTPLATEDAMAGE%"),
				sublime.CompletionItem(trigger="CHESTPLATEDURABILITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Durability of the Players chestplate", completion="%CHESTPLATEDURABILITY%"),
				sublime.CompletionItem(trigger="CHESTPLATEID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="ID of the Players chestplate", completion="%CHESTPLATEID%"),
				sublime.CompletionItem(trigger="CHESTPLATENAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Displayname of the Players chestplate", completion="%CHESTPLATENAME%"),
				sublime.CompletionItem(trigger="CHUNKUPDATES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Amount of chunk updates", completion="%CHUNKUPDATES%"),
				sublime.CompletionItem(trigger="CLEARCHAT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Clears all messages from the chat window", completion="CLEARCHAT();"),
				sublime.CompletionItem(trigger="CLEARCRAFTING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Cancels any queued crafting jobs", completion="CLEARCRAFTING();"),
				sublime.CompletionItem(trigger="CONFIG", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Switch to the specified configuration", completion="CONFIG(${1:<configname>});"),
				sublime.CompletionItem(trigger="CONFIG", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Loaded config", completion="%CONFIG%"),
				sublime.CompletionItem(trigger="CONTAINERSLOTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Amount of slots in opened container", completion="%CONTAINERSLOTS%"),
				sublime.CompletionItem(trigger="CONTROLS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(controls iterator)", details="Iterates over all existing controls", completion="CONTROLS([layout][:type])"),
				sublime.CompletionItem(trigger="CONTROLID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(controls iterator)" ,details="Internal id of the current control", completion="%CONTROLID%"),
				sublime.CompletionItem(trigger="CONTROLNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(controls iterator)", details="The name set in the control under Control Name", completion="%CONTROLNAME%"),
				sublime.CompletionItem(trigger="CONTROLTYPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(controls iterator)" ,details="Type of the current control", completion="%CONTROLTYPE%"),
				sublime.CompletionItem(trigger="COOLDOWN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Cooldown", completion="%COOLDOWN%"),
				sublime.CompletionItem(trigger="CRAFT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Queues an auto-crafting request", completion="CRAFT(${1:<item>}:${2:[damage]},${3:[amount]},${4:[throw]},${5:[verbose]});"),
				sublime.CompletionItem(trigger="CRAFTANDWAIT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Queues an auto-crafting request and waits", completion="CRAFTANDWAIT(${1:<item>}:${2:[damage]},${3:[amount]},${4:[throw]},${5:[verbose]});"),
				sublime.CompletionItem(trigger="DATE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Current date in the format year-month-day", completion="%DATE%"),
				sublime.CompletionItem(trigger="DATETIME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Current date and time in the format year-month-day hour:minute:second", completion="%DATETIME%"),
				sublime.CompletionItem(trigger="DAY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Number of day", completion="%DAY%"),
				sublime.CompletionItem(trigger="DAYTICKS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="TICKS value modulo 24000 and shifted back 6000 so that 0 aligns with midnight ", completion="%DAYTICKS%"),
				sublime.CompletionItem(trigger="DAYTIME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Ingame time in the format hh:mm", completion="%DAYTIME%"),
				sublime.CompletionItem(trigger="DEC", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Decrements the specified counter by 1 or by the specified amount", completion="DEC(#${1:<var>},${2:[amount]});"),
				sublime.CompletionItem(trigger="DECODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Converts an string from base64 back to an normal string", completion="DECODE(${1:<input>},${2:[&output]});"),
				sublime.CompletionItem(trigger="DIFFICULTY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Difficulty of the world", completion="%DIFFICULTY%"),
				sublime.CompletionItem(trigger="DIMENSION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Dimension the Player is in", completion="%DIMENSION%"),
				sublime.CompletionItem(trigger="DIRECTION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Direction the Player is looking at, shortened to the first character", completion="%DIRECTION%"),
				sublime.CompletionItem(trigger="DISCONNECT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Disconnects from the current game or server", completion="DISCONNECT();"),
				sublime.CompletionItem(trigger="DISPLAYHEIGHT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Height of the minecraft window", completion="%DISPLAYHEIGHT%"),
				sublime.CompletionItem(trigger="DISPLAYNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Player's displayname", completion="%DISPLAYNAME%"),
				sublime.CompletionItem(trigger="DISPLAYWIDTH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Width of the minecraft window", completion="%DISPLAYWIDTH%"),
				sublime.CompletionItem(trigger="DURABILITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Durability of the equipped item", completion="%DURABILITY%"),
				sublime.CompletionItem(trigger="ECHO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sends the specified message to the server", completion="ECHO(${1:<text>});"),
				sublime.CompletionItem(trigger="EFFECTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(effects iterator)", details="Iterates over all currently applied effects", completion="EFFECTS"),
				sublime.CompletionItem(trigger="EFFECT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(effects iterator)", details="Internal string id of the effect", completion="%EFFECT%"),
				sublime.CompletionItem(trigger="EFFECTID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(effects iterator)", details="Internal numeric id of the effect", completion="%EFFECTID%"),
				sublime.CompletionItem(trigger="EFFECTNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(effects iterator)", details="Display name of the effect", completion="%EFFECTNAME%"),
				sublime.CompletionItem(trigger="EFFECTPOWER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(effects iterator)", details="Power of the effect", completion="%EFFECTPOWER%"),
				sublime.CompletionItem(trigger="EFFECTTIME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(effects iterator)", details="Remaining time of the effect in seconds", completion="%EFFECTTIME%"),
				sublime.CompletionItem(trigger="ENCHANTMENTS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(enchantments iterator)", details="Iterates over all enchantments on the equipped item", completion="ENCHANTMENTS"),
				sublime.CompletionItem(trigger="ENCHANTMENT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(enchantments iterator)", details="Display name of the enchantment", completion="%ENCHANTMENT%"),
				sublime.CompletionItem(trigger="ENCHANTMENTNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(enchantments iterator)", details="Only the name of the enchantment", completion="%ENCHANTMENTNAME%"),
				sublime.CompletionItem(trigger="ENCHANTMENTPOWER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(enchantments iterator)", details="Power of the enchantment", completion="%ENCHANTMENTPOWER%"),
				sublime.CompletionItem(trigger="ENCODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Converts an string to base 64", completion="ENCODE(${1:<input>},&${2:[output]});"),
				sublime.CompletionItem(trigger="ENV", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(env iterator)", details="Iterates over all available variables", completion="ENV"),
				sublime.CompletionItem(trigger="VARNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(env iterator)", details="Contains the variable name", completion="%VARNAME%"),
				sublime.CompletionItem(trigger="EXEC", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Creates a task by running the specified script file", completion="EXEC(${1:<file.txt>},${2:[taskname]},${3:[params]});"),
				sublime.CompletionItem(trigger="FILTER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Indicate that this chat meesage should be filtered and terminate", completion="FILTER;"),
				sublime.CompletionItem(trigger="FLYING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Whether the Player is flying", completion="%FLYING%"),
				sublime.CompletionItem(trigger="FOG", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Toggles render distance, or optionally specify render distance", completion="FOG(${1:[value]});"),
				sublime.CompletionItem(trigger="FOV", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the FOV angle in degrees, specifying time causes the value to change smoothly", completion="FOV(${1:<value>},${2:[time]});"),
				sublime.CompletionItem(trigger="FOV", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Field of View", completion="%FOV%"),
				sublime.CompletionItem(trigger="FPS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Frames per Second", completion="%FPS%"),
				sublime.CompletionItem(trigger="GAMEMODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Gamemode of the player as a string", completion="%GAMEMODE%"),
				sublime.CompletionItem(trigger="GAMMA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the brightness value (percent), specifying time causes the value to change smoothly", completion="GAMMA(${1:<value>},${2:[time]});"),
				sublime.CompletionItem(trigger="GAMMA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Brightness level", completion="%GAMMA%"),
				sublime.CompletionItem(trigger="GETID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Gets the ID and data value of the block at the specified coordinates", completion="GETID(${1:<x>},${2:<y>},${3:<z>},&${4:[idvar]},#${5:[datavar]},&${6:[variants]});"),
				sublime.CompletionItem(trigger="GETIDREL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Gets the ID and data value of the block at the specified coordinates relative to the player", completion="GETIDREL(${1:<dx>},${2:<dy>},${3:<dz>},&${4:[idvar]},#${5:[datavar]},&${6:[variants]});"),
				sublime.CompletionItem(trigger="GETITEMINFO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Gets the name and other info for the specified item id", completion="GETITEMINFO(${1:<item>}:${2:[damage]},&${3:[namevar]},#${4:[maxstacksize]},&${5:[type]},&${6:[dropid]},#${7:[maxdurability]});"),
				sublime.CompletionItem(trigger="GETPROPERTY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Returns the value of the specified property from the specified GUI control", completion="GETPROPERTY(${1:<control>},${2:<property>});"),
				sublime.CompletionItem(trigger="GETSLOT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Gets the id of the slot containing an item matching the specified item id", completion="GETSLOT(${1:<item>}:${2:[damage]},#${3:<slotid>},${4:[startfromslotid]});"),
				sublime.CompletionItem(trigger="GETSLOTITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Gets information about the item in the specified slot", completion="GETSLOTITEM(${1:<slotid>},&${2:<idvar>},#${3:[stacksizevar]},#${4:[datavar]});"),
				sublime.CompletionItem(trigger="GUI", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Opens the specified gui screen", completion="GUI(${1:[name]});"),
				sublime.CompletionItem(trigger="GUI", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Name of the currently open GUI", completion="%GUI%"),
				sublime.CompletionItem(trigger="HEALTH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Health points (each icon equals 2 points)", completion="%HEALTH%"),
				sublime.CompletionItem(trigger="HELMDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Maximum uses of the Players helm", completion="%HELMDAMAGE%"),
				sublime.CompletionItem(trigger="HELMDURABILITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Durability of the Players helm", completion="%HELMDURABILITY%"),
				sublime.CompletionItem(trigger="HELMID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="ID of the Players helm", completion="%HELMID%"),
				sublime.CompletionItem(trigger="HELMNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Displayname of the Players helm", completion="%HELMNAME%"),
				sublime.CompletionItem(trigger="HOSTILEVOLUME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Volume level for Hostile Creatures", completion="%HOSTILEVOLUME%"),
				sublime.CompletionItem(trigger="HUNGER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Hunger points (each icon equals 2 points)", completion="%HUNGER%"),
				sublime.CompletionItem(trigger="IIF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Inline IF statement", completion="IIF(${1:<condition>},${2:<truetext>},${3:[falsetext]});"),
				sublime.CompletionItem(trigger="IMPORT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Overlay the specified configuration", completion="IMPORT(${1:<configname>});"),
				sublime.CompletionItem(trigger="INC", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Increments the specified counter by 1 or by the specified amount", completion="INC(#${1:<var>},${2:[amount]});"),
				sublime.CompletionItem(trigger="INDEXOF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Gets the first index of a item", completion="INDEXOF(${1:<array>}[],#${2:<outvar>},${3:<searchfor>},${4:[casesensitiv]});"),
				sublime.CompletionItem(trigger="INVENTORYDOWN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Scrolls the specified number of slots down through the hotbar", completion="INVENTORYDOWN(${1:[amount]});"),
				sublime.CompletionItem(trigger="INVENTORYUP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Scrolls the specified number of slots up through the hotbar", completion="INVENTORYUP(${1:[amount]});"),
				sublime.CompletionItem(trigger="INVSLOT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Selected inventory slot", completion="%INVSLOT%"),
				sublime.CompletionItem(trigger="ISRUNNING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Returns whether the specified macro is currently running", completion="ISRUNNING(${1:<macro>});"),
				sublime.CompletionItem(trigger="ITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="ID of the equipped item", completion="%ITEM%"),
				sublime.CompletionItem(trigger="ITEMCODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Internal code for the equipped item", completion="%ITEMCODE%"),
				sublime.CompletionItem(trigger="ITEMDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Maximum uses of the equipped item", completion="%ITEMDAMAGE%"),
				sublime.CompletionItem(trigger="ITEMID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Gets the legacy (numeric) ID for the specified item", completion="ITEMID(${1:<item>});"),
				sublime.CompletionItem(trigger="ITEMIDDMG", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="ID and durability seperated by a colon of the equipped item", completion="%ITEMIDDMG%"),
				sublime.CompletionItem(trigger="ITEMNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Displayname for the equipped item", completion="%ITEMNAME%"),
				sublime.CompletionItem(trigger="ITEMNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Get the item descriptor for a legacy (numeric) item ID", completion="ITEMNAME(${1:<id>});"),
				sublime.CompletionItem(trigger="ITEMUSEPCT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Previous value as percent of total useage time", completion="%ITEMUSEPCT%"),
				sublime.CompletionItem(trigger="ITEMUSETICKS ", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="All usable items increase this value once per tick", completion="%ITEMUSETICKS%"),
				sublime.CompletionItem(trigger="JOIN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Combines values inside array with glue", completion="JOIN(${1:<glue>},${2:<array>}[],&${3:[output]});"),
				sublime.CompletionItem(trigger="JOINEDPLAYER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onPlayerJoined) Player name of the newly joined player", completion="%JOINEDPLAYER%"),
				sublime.CompletionItem(trigger="KEY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Activates the specified key binding for 1 tick", completion="KEY(${1:<bind>});"),
				sublime.CompletionItem(trigger="KEYDOWN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the specified key binding state to pressed, only works with pressable bindings", completion="KEYDOWN(${1:<bind>});"),
				sublime.CompletionItem(trigger="KEYID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Key ID of the key that started this script", completion="%KEYID%"),
				sublime.CompletionItem(trigger="KEYNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Keyname of the key that started this script", completion="%KEYNAME%"),
				sublime.CompletionItem(trigger="KEYUP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the specified key binding state to unpressed, only works with pressable bindings", completion="KEYUP(${1:<bind>});"),
				sublime.CompletionItem(trigger="LCASE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Converts the input string to lower case and stores it in output", completion="LCASE(${1:<input>},&${2:[output]});"),
				sublime.CompletionItem(trigger="LEGGINGSDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Maximum uses of the Players leggings", completion="%LEGGINGSDAMAGE%"),
				sublime.CompletionItem(trigger="LEGGINGSDURABILITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Durability of the Players leggings", completion="%LEGGINGSDURABILITY%"),
				sublime.CompletionItem(trigger="LEGGINGSID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="ID of the Players leggings", completion="%LEGGINGSID%"),
				sublime.CompletionItem(trigger="LEGGINGSNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Displayname of the Players leggings", completion="%LEGGINGSNAME%"),
				sublime.CompletionItem(trigger="LEVEL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="XP level", completion="%LEVEL%"),
				sublime.CompletionItem(trigger="LIGHT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Light level at current location", completion="%LIGHT%"),
				sublime.CompletionItem(trigger="LOCALDIFFICULTY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Local difficulty of the world", completion="%LOCALDIFFICULTY%"),
				sublime.CompletionItem(trigger="LOG", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Shows the specified text only on the client-side in the chat window", completion="LOG(${1:<text>});"),
				sublime.CompletionItem(trigger="LOGRAW", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Similar to minecraft tellraw command", completion="LOGRAW(${1:<json>});"),
				sublime.CompletionItem(trigger="LOGTO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Outputs the specified text into the specified target", completion="LOGTO(${1:<target>},${2:<text>});"),
				sublime.CompletionItem(trigger="LOOK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Faces the player in the specified direction", completion="LOOK(${1:<yaw>},${2:[pitch]},${3:[time]});"),
				sublime.CompletionItem(trigger="LOOKS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Smoothly turnes the player to the specified direction", completion="LOOKS(${1:<yaw>},${2:[pitch]},${3:[time]});"),
				sublime.CompletionItem(trigger="RUNNING", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(running iterator)", details="Iterates over all currently running macros", completion="RUNNING"),
				sublime.CompletionItem(trigger="MACROID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(running iterator)", details="Internal id of the macro", completion="%MACROID%"),
				sublime.CompletionItem(trigger="MACRONAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(running iterator)", details="Display name of the macro", completion="%MACRONAME%"),
				sublime.CompletionItem(trigger="MACROTIME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(running iterator)", details="The time the macro is already running in seconds", completion="%MACROTIME%"),
				sublime.CompletionItem(trigger="MAINHANDCOOLDOWN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="mainhand cooldown", completion="%MAINHANDCOOLDOWN%"),
				sublime.CompletionItem(trigger="MAINHANDDURABILITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Durability of the mainhand item", completion="%MAINHANDDURABILITY%"),
				sublime.CompletionItem(trigger="MAINHANDITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="ID of the mainhand item", completion="%MAINHANDITEM%"),
				sublime.CompletionItem(trigger="MAINHANDITEMCODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Internal code for the mainhand item", completion="%MAINHANDITEMCODE%"),
				sublime.CompletionItem(trigger="MAINHANDITEMDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Maximum uses of the mainhand item", completion="%MAINHANDITEMDAMAGE%"),
				sublime.CompletionItem(trigger="MAINHANDITEMIDDMG", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="ID and durability seperated by a colon of the mainhand item", completion="%MAINHANDITEMIDDMG%"),
				sublime.CompletionItem(trigger="MAINHANDITEMNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Displayname for the mainhand item", completion="%MAINHANDITEMNAME%"),
				sublime.CompletionItem(trigger="MAINHANDSTACKSIZE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Stacksize of the mainhand item", completion="%MAINHANDSTACKSIZE%"),
				sublime.CompletionItem(trigger="MATCH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Runs a regular expression match on the subject", completion="MATCH(${1:<subject>},${2:<pattern>},&${3:[target]},${4:[group]},${5:[default]});"),
				sublime.CompletionItem(trigger="MAXPLAYERS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Amount of players the server can hold", completion="%MAXPLAYERS%"),
				sublime.CompletionItem(trigger="MODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Gamemode of the player as a number", completion="%MODE%"),
				sublime.CompletionItem(trigger="MODIFY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Set new content for this chat message", completion="MODIFY(${1:<newmessage>});"),
				sublime.CompletionItem(trigger="MUSIC", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Volume level for Music", completion="%MUSIC%"),
				sublime.CompletionItem(trigger="MUSIC", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the music volume, specifying time causes the value to change smoothly", completion="MUSIC(${1:<value>},${2:[time]});"),
				sublime.CompletionItem(trigger="NEUTRALVOLUME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Volume level for Friendly Creatures", completion="%NEUTRALVOLUME%"),
				sublime.CompletionItem(trigger="NEXT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Completes a for or foreach loop", completion="NEXT;"),
				sublime.CompletionItem(trigger="OFFHANDCOOLDOWN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Offhand cooldown", completion="%OFFHANDCOOLDOWN%"),
				sublime.CompletionItem(trigger="OFFHANDDURABILITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Durability of the offhand item", completion="%OFFHANDDURABILITY%"),
				sublime.CompletionItem(trigger="OFFHANDITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="ID of the offhand item", completion="%OFFHANDITEM%"),
				sublime.CompletionItem(trigger="OFFHANDITEMCODE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Internal code for the offhand item", completion="%OFFHANDITEMCODE%"),
				sublime.CompletionItem(trigger="OFFHANDITEMDAMAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Maximum uses of the offhand item", completion="%OFFHANDITEMDAMAGE%"),
				sublime.CompletionItem(trigger="OFFHANDITEMIDDMG", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="ID and durability seperated by a colon of the offhand item", completion="%OFFHANDITEMIDDMG%"),
				sublime.CompletionItem(trigger="OFFHANDITEMNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Displayname for the offhand item", completion="%OFFHANDITEMNAME%"),
				sublime.CompletionItem(trigger="OFFHANDSTACKSIZE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Stacksize of the offhand item", completion="%OFFHANDSTACKSIZE%"),
				sublime.CompletionItem(trigger="OLDINVSLOT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onInventorySlotChange) Selected inventory slot before it was changed", completion="%OLDINVSLOT%"),
				sublime.CompletionItem(trigger="ONLINEPLAYERS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Amount of players currently on the server", completion="%ONLINEPLAYERS%"),
				sublime.CompletionItem(trigger="OXYGEN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Air Level (from 0 to 300)", completion="%OXYGEN%"),
				sublime.CompletionItem(trigger="PASS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Indicate that this chat message should PASS the filter and terminate", completion="PASS;"),
				sublime.CompletionItem(trigger="PICK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Selects the specified item id if it is on the hotbar", completion="PICK(${1:<item>}:${2:[damage]},${3:<item>}:${4:[damage]}${5:,...});"),
				sublime.CompletionItem(trigger="PICKUPAMOUNT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onPickupItem) Amount of items picked up", completion="%PICKUPAMOUNT%"),
				sublime.CompletionItem(trigger="PICKUPDATA", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onPickupItem) Metadata of the picked up item", completion="%PICKUPDATA%"),
				sublime.CompletionItem(trigger="PICKUPID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onPickupItem) Item id of the picked up item", completion="%PICKUPID%"),
				sublime.CompletionItem(trigger="PICKUPITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onPickupItem) Display name of the picked up item", completion="%PICKUPITEM%"),
				sublime.CompletionItem(trigger="PITCH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Pitch of the player", completion="%PITCH%"),
				sublime.CompletionItem(trigger="PLACESIGN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Places a sign in the world with the specified text", completion="PLACESIGN(${1:[line1]},${2:[line2]},${3:[line3]},${4:[line4]},${5:[showgui]});"),
				sublime.CompletionItem(trigger="PLAYER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Player's name", completion="%PLAYER%"),
				sublime.CompletionItem(trigger="PLAYERS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(players iterator)", details="Iterates over all online players", completion="PLAYERS"),
				sublime.CompletionItem(trigger="PLAYERNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(players iterator)", details="The current player", completion="%PLAYERNAME%"),
				sublime.CompletionItem(trigger="PLAYERVOLUME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Volume level for Players", completion="%PLAYERVOLUME%"),
				sublime.CompletionItem(trigger="PLAYSOUND", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Plays the specified sound", completion="PLAYSOUND(${1:<sound>},${2:[volume]});"),
				sublime.CompletionItem(trigger="POP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Removes the last entry from the end of array and stores it in outvar", completion="POP(${1:<array>}[],${2:<outvar>});"),
				sublime.CompletionItem(trigger="POPUPMESSAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Display a message in the area above the hotbar", completion="POPUPMESSAGE(${1:<message>},${2:[animate]});"),
				sublime.CompletionItem(trigger="PRESS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Injects the specified key event directly into the keyboard buffer for 1 tick", completion="PRESS(${1:<lwjgl_name>},${2:[deep]});"),
				sublime.CompletionItem(trigger="PROMPT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Displays a prompt by parsing the params in paramstring", completion="PROMPT(&${1:<target>},${2:<paramstring>},${3:[prompt]},${4:[override]},${5:[default]});"),
				sublime.CompletionItem(trigger="PROPERTIES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, annotation="(properties iterator)", details="Iterates over all properties of the block you are looking at", completion="PROPERTIES"),
				sublime.CompletionItem(trigger="PROPNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(properties iterator)", details="The name of the current property", completion="%PROPNAME%"),
				sublime.CompletionItem(trigger="PROPVALUE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, annotation="(properties iterator)", details="The value of the current property", completion="%PROPVALUE%"),
				sublime.CompletionItem(trigger="PUSH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Appends value to the end of array[]", completion="PUSH(${1:<array>}[],${2:<value>});"),
				sublime.CompletionItem(trigger="PUT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Inserts value at the first empty point in array[]", completion="PUT(${1:<array>}[],${2:<value>});"),
				sublime.CompletionItem(trigger="RAIN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Rain level", completion="%RAIN%"),
				sublime.CompletionItem(trigger="RANDOM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Assigns a random number between min and max to target", completion="RANDOM(#${1:<target>},${2:[max]},${3:[min])};"),
				sublime.CompletionItem(trigger="REASON", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="(onAutoCraftingComplete) The reason why the crafting was completed or aborted", completion="%REASON%"),
				sublime.CompletionItem(trigger="RECORDVOLUME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Volume level for Jukebox/Noteblocks", completion="%RECORDVOLUME%"),
				sublime.CompletionItem(trigger="REGEXREPLACE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Replace all matches of pattern with replace in &subject", completion="REGEXREPLACE(&${1:<subject>},${2:<pattern>},${3:[replace]});"),
				sublime.CompletionItem(trigger="RELOADRESOURCES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Reloads resource packs, same as pressing F3 + T", completion="RELOADRESOURCES;"),
				sublime.CompletionItem(trigger="REPL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Access the REPL interface", completion="REPL;"),
				sublime.CompletionItem(trigger="REPLACE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Replace all occurrences of search with replace in &subject", completion="REPLACE(&${1:<subject>},${2:<search>},${3:[replace]});"),
				sublime.CompletionItem(trigger="RESOURCEPACKS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the resource pack stack to the order matching the specified patterns", completion="RESOURCEPACKS(${1:[pattern]},${2:[pattern...]});"),
				sublime.CompletionItem(trigger="RESOURCEPACKS[]", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Array of selected resource packs", completion="%RESOURCEPACKS[]%"),
				sublime.CompletionItem(trigger="RESPAWN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Respawns the player if you are dead", completion="RESPAWN();"),
				sublime.CompletionItem(trigger="SATURATION", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Saturation level (normally hidden from the Player)", completion="%SATURATION%"),
				sublime.CompletionItem(trigger="SCREEN", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Name of the current custom GUI", completion="%SCREEN%"),
				sublime.CompletionItem(trigger="SCREENNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Display name of the current custom GUI", completion="%SCREENNAME%"),
				sublime.CompletionItem(trigger="SEED", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Seed of the world (only available in SP)", completion="%SEED%"),
				sublime.CompletionItem(trigger="SELECTCHANNEL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Selects channel", completion="SELECTCHANNEL(${1:<channel>});"),
				sublime.CompletionItem(trigger="SENDMESSAGE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sends a message", completion="SENDMESSAGE(${1:[params]});"),
				sublime.CompletionItem(trigger="SENSITIVITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Sensitivity", completion="%SENSITIVITY%"),
				sublime.CompletionItem(trigger="SENSITIVITY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the mouse sensitivity, specifying time causes the value to change smoothly", completion="SENSITIVITY(${1:<value>},${2:[time]});"),
				sublime.CompletionItem(trigger="SERVER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="IP of the server", completion="%SERVER%"),
				sublime.CompletionItem(trigger="SERVERMOTD", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Motto of the day of the server", completion="%SERVERMOTD%"),
				sublime.CompletionItem(trigger="SERVERNAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Name of the server", completion="%SERVERNAME%"),
				sublime.CompletionItem(trigger="SET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the value of target to value", completion="SET(${1:<target>},${2:[value]});"),
				sublime.CompletionItem(trigger="SETLABEL", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the text (and optionally binding) of the specified label", completion="SETLABEL(${1:<labelname>},${2:<text>},${3:[binding]});"),
				sublime.CompletionItem(trigger="SETPROPERTY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the value of the specified property on the specified GUI control", completion="SETPROPERTY(${1:<control>},${2:<property>},${3:<value>});"),
				sublime.CompletionItem(trigger="SETRES", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the size of the minecraft game window", completion="SETRES(${1:<width>},${2:<height>});"),
				sublime.CompletionItem(trigger="SETSLOTITEM", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Creative mode only, set the contents of a hot bar slot", completion="SETSLOTITEM(${1:<item>}:${2:[damage]},${3:[slot]},${4:[amount]});"),
				sublime.CompletionItem(trigger="SHADERGROUP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Selected shader", completion="%SHADERGROUP%"),
				sublime.CompletionItem(trigger="SHADERGROUP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the active shader group to the shader matching path", completion="SHADERGROUP(${1:[path]});"),
				sublime.CompletionItem(trigger="SHADERGROUPS[]", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Array of available shaders", completion="%SHADERGROUPS[]%"),
				sublime.CompletionItem(trigger="SHOWGUI", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Show a custom gui screen, creates it if it doesn't exist", completion="SHOWGUI(${1:<screen>},${2:[esc_screen]},${3:[macro_keys]});"),
				sublime.CompletionItem(trigger="SIGNTEXT[]", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Array of lines on a sign the Player is looking at", completion="%SIGNTEXT[]%"),
				sublime.CompletionItem(trigger="SLOT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Selects the specified slot on the hot bar", completion="SLOT(${1:<slot>});"),
				sublime.CompletionItem(trigger="SLOTCLICK", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Simulates clicking on the specified slot in the current GUI", completion="SLOTCLICK(${1:<slot>},${2:[button]},${3:[shift]});"),
				sublime.CompletionItem(trigger="SOUND", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Master Volume level", completion="%SOUND%"),
				sublime.CompletionItem(trigger="SPLIT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Splits the supplied source string on every delimiter into output[]", completion="SPLIT(${1:<delimiter>},${2:<source>},${3:[output]}[]);"),
				sublime.CompletionItem(trigger="SPRINT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the player state to sprinting if sufficient stamina (food)", completion="SPRINT();"),
				sublime.CompletionItem(trigger="SQRT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Calculate the rounded square root of value and store it in #outvar", completion="SQRT(${1:<value>},#${2:[outvar]});"),
				sublime.CompletionItem(trigger="STACKSIZE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Stack size of the equipped item", completion="%STACKSIZE%"),
				sublime.CompletionItem(trigger="STOP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Stops the current macro, or macros matching the specified ID", completion="STOP(${1:[id]});"),
				sublime.CompletionItem(trigger="STORE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Stores a value into one of the predefined parameter lists", completion="STORE(${1:<type>},${2:[name]});"),
				sublime.CompletionItem(trigger="STOREOVER", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Stores a value into one of the predefined parameter lists", completion="STOREOVER(${1:<type>},${2:[name]});"),
				sublime.CompletionItem(trigger="STRIP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Strips all formatting codes from the specified text and assigns the result to &target", completion="STRIP(&${1:<target>},${2:<text>});"),
				sublime.CompletionItem(trigger="TICKS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="current world time value (which will be a static number if doDayNightCycle game rule is false)", completion="%TICKS%"),
				sublime.CompletionItem(trigger="TILEID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Gets the legacy (numeric) ID for the specified tile", completion="TILEID(${1:<item>});"),
				sublime.CompletionItem(trigger="TILENAME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Get the descriptor for a legacy (numeric) tile ID", completion="TILENAME(${1:<id>});"),
				sublime.CompletionItem(trigger="TIME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Stores the current time and date into &target, optionally using format specified", completion="TIME(&${1:<target>},${2:[format]});"),
				sublime.CompletionItem(trigger="TIME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Current time in the format hour:minute:second", completion="%TIME%"),
				sublime.CompletionItem(trigger="TIMESTAMP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="UNIX Timestamp", completion="%TIMESTAMP%"),
				sublime.CompletionItem(trigger="TITLE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Displays the specified custom title", completion="TITLE(${1:[title]},${2:[subtitle]},${3:[inticks]},${4:[showticks]},${5:[outticks]});"),
				sublime.CompletionItem(trigger="TOAST", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Displays an user-defined toast", completion="TOAST(${1:[type]},${2:[icon]},${3:[text1]},${4:[text2]},${5:[ticks]});"),
				sublime.CompletionItem(trigger="TOGGLE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Toggles the specified boolean flag value", completion="TOGGLE(${1:[flag]});"),
				sublime.CompletionItem(trigger="TOGGLEKEY", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Toggles the pressed state of the specified key binding, only works with pressable bindings", completion="TOGGLEKEY(${1:<bind>});"),
				sublime.CompletionItem(trigger="TOTALTICKS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="current total world time (which increases all the time regardless of the gamerule doDayNightCycle)", completion="%TOTALTICKS%"),
				sublime.CompletionItem(trigger="TOTALXP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Total amount of experience points", completion="%TOTALXP%"),
				sublime.CompletionItem(trigger="TYPE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Injects the specified key sequence directly into the keyboard buffer at a rate of 1 key per tick", completion="TYPE(${1:<text>});"),
				sublime.CompletionItem(trigger="UCASE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Converts the input string to upper case and stores it in output", completion="UCASE(${1:<input>},&${2:[output]});"),
				sublime.CompletionItem(trigger="UNIMPORT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Remove the specified configuration overlay if active", completion="UNIMPORT();"),
				sublime.CompletionItem(trigger="UNIQUEID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Returns a new UUID everytime it is accessed", completion="%UNIQUEID%"),
				sublime.CompletionItem(trigger="UNSET", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Un-sets the specified flag variable", completion="UNSET(${1:<flag>});"),
				sublime.CompletionItem(trigger="UNSPRINT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the player state to not sprinting", completion="UNSPRINT();"),
				sublime.CompletionItem(trigger="UUID", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="UUID of the Player", completion="%UUID%"),
				sublime.CompletionItem(trigger="VEHICLE", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Vehicle type", completion="%VEHICLE%"),
				sublime.CompletionItem(trigger="VEHICLEHEALTH", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Vehicle health", completion="%VEHICLEHEALTH%"),
				sublime.CompletionItem(trigger="VOLUME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Sets the sound volume for the specified category", completion="VOLUME(${1:<value>},${2:[category]});"),
				sublime.CompletionItem(trigger="WAIT", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Pauses the script for the time specified", completion="WAIT(${1:<time>});"),
				sublime.CompletionItem(trigger="WALKTO", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_KEYWORD, details="Was never offically in the mod", completion="WALKTO(${1:<x>},${2:<y>},${3:<z>},${4:[speed]},${5:[radius]});"),
				sublime.CompletionItem(trigger="WEATHERVOLUME", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Volume level for Weather", completion="%WEATHERVOLUME%"),
				sublime.CompletionItem(trigger="XP", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Current amount of experience points", completion="%XP%"),
				sublime.CompletionItem(trigger="XPOS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Position in X direction", completion="%XPOS%"),
				sublime.CompletionItem(trigger="XPOSF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="The position in X direction with three decimal places after the comma as a string", completion="%XPOSF%"),
				sublime.CompletionItem(trigger="YAW", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Yaw of the player", completion="%YAW%"),
				sublime.CompletionItem(trigger="YPOS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Position in Y direction", completion="%YPOS%"),
				sublime.CompletionItem(trigger="YPOSF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="The position in Y direction with three decimal places after the comma as a string", completion="%YPOSF%"),
				sublime.CompletionItem(trigger="ZPOS", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="Position in Z direction", completion="%ZPOS%"),
				sublime.CompletionItem(trigger="ZPOSF", completion_format=sublime.COMPLETION_FORMAT_SNIPPET, kind=sublime.KIND_VARIABLE, details="The position in Z direction with three decimal places after the comma as a string", completion="%ZPOSF%")
			], flags=sublime.INHIBIT_EXPLICIT_COMPLETIONS)