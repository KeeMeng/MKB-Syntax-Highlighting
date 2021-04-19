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
			"default" :	["endswitch"]
		}
		self.openings = "IF|ELSEIF|ELSE|FOR|DO|UNSAFE|POLLEVENT|SWITCH|CASE|DEFAULT"
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
				teststring = re.match("elseif|else|endif|next|until|while|loop|endunsafe|endswitch|case|default", line, re.IGNORECASE)
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


# 1000+ Lines of auto complete below!!
class mkbcompletions(sublime_plugin.EventListener):
	def on_query_completions(self, view, prefix, locations):
		if view.match_selector(view.line(locations[0]).a, "comment.mkb"):
			return ([],sublime.INHIBIT_EXPLICIT_COMPLETIONS)
		elif view.match_selector(0, "source.mkb") and config("autocomplete_caps"):
			return ([
				["IF\tExecuted when the <condition> evaluates to true", "IF(${1:<condition>});\n	$2\nENDIF;\n$3"],
				["IFBEGINSWITH\tExecutes when the <haystack> contains the <pattern>", "IFBEGINSWITH(${1:<haystack>},${2:<needle>});\n	$3\nENDIF;\n$4"],
				["IFCONTAINS\tExecutes when the <haystack> contains the <pattern>", "IFCONTAINS(${1:<haystack>},${2:<needle>});\n	$3\nENDIF;\n$4"],
				["IFENDSWITH\tExecutes when the <haystack> contains the <pattern>", "IFENDSWITH(${1:<haystack>},${2:<needle>});\n	$3\nENDIF;\n$4"],
				["IFMATCHES\tExecutes when the <subject> matches the <pattern>", "IFMATCHES(${1:<subject>},${2:<pattern>},${3:&[target]},${4:[group]});\n	$5\nENDIF;\n$6"],

				["FOR\tfor(var,start,end)", "FOR(#${1:<var>},${2:<start>},${3:<end>});\n	$4\nNEXT;\n$5"],
				["FOR\tfor(var = start to end)", "FOR(#${1:<var>} = ${2:<start>} to ${3:<end>});\n	$4\nNEXT;\n$5"],
				["FOR\tfor(var = start to end step)", "FOR(#${1:<var>} = ${2:<start>} to ${3:<end>} step ${4:<step>});\n	$5\nNEXT;\n$6"],
				["FOREACH\tforeach(iterator)", "FOREACH(${1:<iterator>});\n	$2\nNEXT;\n$3"],
				["FOREACH\tforeach(array,content,index)", "FOREACH(${1:<&array>}[],${2:<&content>},#${3:[index]});\n	$4\nNEXT;\n$5"],
				["FOREACH\tforeach(array as content)", "FOREACH(${1:<&array>}[] as &${2:<content>});\n	$3\nNEXT;\n$4"],
				["FOREACH\tforeach(array as index => content)", "FOREACH(${1:<&array>}[] as #${2:<index>} => ${3:<&content>});\n	$4\nNEXT;\n$5"],
				["DO\t…loop", "DO(${1:[count]});\n	$2\nLOOP;$3"],
				["DO\t…while", "DO(${1:[count]});\n	$2\nWHILE(${3:<condition>});$4"],
				["DO\t…until", "DO(${1:[count]});\n	$2\nUNTIL(${3:<condition>});$4"],

				["ELSE\tExecutes if no if-clause before evaluated to true", "ELSE;\n	$1"],
				["ELSEIF", "ELSEIF(${1:<condition>});\n	$2"],
				["LOOP\tCloses a do loop", "LOOP;\n$1"],
				["WHILE\tExits do loop if condition is not met", "WHILE(${1:<condition>});\n$2"],
				["UNTIL\tExits do loop if condition is met", "UNTIL(${1:<condition>});\n$2"],

				["ELSEIFBEGINSWITH", "ELSEIFBEGINSWITH(${1:<haystack>},${2:<needle>});\n	$3"],
				["ELSEIFCONTAINS", "ELSEIFCONTAINS(${1:<haystack>},${2:<needle>});\n	$3"],
				["ELSEIFENCHANTED", "ELSEIFENCHANTED(${1:<slot>},&${2:[item]},#${3:[stacksize]},#${4:[datavar]},&${5:[nbt]});\n	$6"],
				["ELSEIFENDSWITH", "ELSEIFENDSWITH(${1:<haystack>},${2:<needle>});\n	$3"],
				["ELSEIFFILEEXIST", "ELSEIFFILEEXISTS(${1:<path>},${2:[expression if file should be created if missing]});\n	$3"],
				["ELSEIFININV", "ELSEIFININV(${1:[mode]},${2:<items>});\n	$3"],
				["ELSEIFINVISFULL", "ELSEIFINVISFULL(${1:[item]});\n	$2"],
				["ELSEIFMATCHES", "ELSEIFMATCHES(${1:<subject>},${2:<pattern>},&${3:[target]},${4:[group]});\n	$5"],
				["ELSEIFCANHARVESTBLOCK", "ELSEIFCANHARVESTBLOCK(${1:<blockid>});\n	$2"],

				["WHILEBEGINSWITH", "WHILEBEGINSWITH(${1:<haystack>},${2:<needle>});\n$3"],
				["WHILECONTAINS", "WHILECONTAINS(${1:<haystack>},${2:<needle>});\n$3"],
				["WHILEENCHANTED", "WHILEENCHANTED(${1:<slot>},&${2:[item]},#${3:[stacksize]},#${4:[datavar]},&${5:[nbt]});\n$6"],
				["WHILEENDSWITH", "WHILEENDSWITH(${1:<haystack>},${2:<needle>});\n$3"],
				["WHILEFILEEXIST", "WHILEFILEEXISTS(${1:<path>},${2:[expression if file should be created if missing]});\n$3"],
				["WHILEININV", "WHILEININV(${1:[mode]},${2:<items>});\n$3"],
				["WHILEINVISFULL", "WHILEINVISFULL(${1:[item]});\n$2"],
				["WHILEMATCHES", "WHILEMATCHES(${1:<subject>},${2:<pattern>},&${3:[target]},${4:[group]});\n$5"],
				["WHILECANHARVESTBLOCK", "WHILECANHARVESTBLOCK(${1:<blockid>});\n$2"],

				["UNTILBEGINSWITH", "UNTILBEGINSWITH(${1:<haystack>},${2:<needle>});\n$3"],
				["UNTILCONTAINS", "UNTILCONTAINS(${1:<haystack>},${2:<needle>});\n$3"],
				["UNTILENCHANTED", "UNTILENCHANTED(${1:<slot>},&${2:[item]},#${3:[stacksize]},#${4:[datavar]},&${5:[nbt]});\n$6"],
				["UNTILENDSWITH", "UNTILENDSWITH(${1:<haystack>},${2:<needle>});\n$3"],
				["UNTILFILEEXIST", "UNTILFILEEXISTS(${1:<path>},${2:[expression if file should be created if missing]});\n$3"],
				["UNTILININV", "UNTILININV(${1:[mode]},${2:<items>});\n$3"],
				["UNTILINVISFULL", "UNTILINVISFULL(${1:[item]});\n$2"],
				["UNTILMATCHES", "UNTILMATCHES(${1:<subject>},${2:<pattern>},&${3:[target]},${4:[group]});\n$5"],
				["UNTILCANHARVESTBLOCK", "UNTILCANHARVESTBLOCK(${1:<blockid>});\n$2"],

				["UNSAFE\t…endunsafe", "UNSAFE(${1:<executions>});\n	$2\nENDUNSAFE;\n$3"],
				["ENDUNSAFE\tEnds an active unsafe block", "ENDUNSAFE;\n$1"],

				["SWITCH\tSwitch…Case…Default…Endcase", "SWITCH(${1:<expression>});\n	CASE(${2:<value>});\n		$3\n	DEFAULT;\n		$4\nENDSWITCH;\n$5"],
				["CASE\tcase statement", "CASE(${1:<value>});\n	$2"],

				["TRIM\tremoves whitespace", "&${1:result} = TRIM(&${2:string});"],
				["SHUFFLE\tshuffles an array", "SHUFFLE(${1:array[]});"],
				["EVAL\tevaluates an expression", "${2:&${1:[result]} = }EVAL(&${1:[result]},${3:<expression string>});"],
				["CHAR\tputs set unicode value into &char", "CHAR(${1:<&char>},${2:<decimal unicode value>});"],
				["MOD\tevaluates num1 modulo num2", "MOD(#${1:<result>},${2:<num1>},${3:<num2>});"],
				["OLDNAME\tgets the past names of a user", "OLDNAME(&${1:<names>}[],${2:<username>});"],
				["READFILE\tgets the content of a file", "READFILE(&${1:<content>}[],${2:<filename>});"],
				["READFILE\treads file from path", "${2:&${1:<content>}[] = }READFILE(&${1:[content]}[],${3:<path>});"],
				["UNIX\tgets the s/ms of current timestamp", "${2:#${1:[seconds]} = }UNIX(#${1:[seconds]},#${3:[milliseconds]});"],
				["ADDDOCS\tadds documentation for action", "ADDDOCS(${1:<name of entry>},${2:[usage]},${3:[description]},${4:[return type]});"],
				["LISTDOCS\treturns documentation of action", "&${1:docs}[] = LISTDOCS(${2:[name]});"],
				["CALCYAWTO\t+ y argument for pitch", "CALCYAWTO(${1:<xpos>},${2:<ypos>},${3:<zpos>},#${4:[yaw]},#${5:[dist]},#${6:[pitch]});"],
				["GETSLOTITEM\t+ nbt argument", "GETSLOTITEM(${1:<slotid>},&${2:<itemid>},#${3:[stacksize]},#${4:[datavar]},&${5:[nbt]});"],
				["HTTP\tcreates a http request", "&${1:response} = HTTP(${2:[get|post|put|delete]},${3:<url>},${4:[output stream]},${5:[headers]});"],
				["IFFILEEXISTS\tchecks if a file exists", "IFFILEEXISTS(${1:<path>},${2:[expression]});\n	$3\nENDIF;\n$4"],
				["MKDIR\tcreates directory", "MKDIR(${1:<path>});"],
				["WRITEFILE\twrites array to file", "WRITEFILE(${1:<path>},&${2:<writefile>}[],${3:[append]});"],
				["GETJSONASARRAY\treturns json as key:value array", "&${1:array}[] = GETJSONASARRAY(${2:<json>},${3:[format]});"],
				["GETJSONKEYS\tretuns list of the keys of json", "&${1:keys}[] = GETJSONKEYS(${2:<json>});"],
				["JSONGET\tretuns object of key of specified json", "&${1:object} = JSONGET(${2:<json>},${3:<key>});"],
				["SORT\tsorts the arrays synchronously", "SORT(${1:[asc,dsc]},${2:<array>}[],${3:[array]}[]);"],
				["TEAMMEMBERS\tlists scoreboard team members", "&${1:<members/teams>}[] = TEAMMEMBERS(${2:[team]});"],
				["SCORE\treturns score of player in objective", "<${1:&score|&scores[]|&obectives[]}> = SCORE(${2:[objectivename]},${3:[playername]});"],
				["COUNTDOWNTO\tcountdown to the specified datetime", "COUNTDOWNTO(${1:<until>});"],
				["COUNTDOWNFROM\tcountdown from the specified time", "COUNTDOWNFROM(${1:<start>});"],
				["COUNTUP\tcreates a countup from the current time", "COUNTUP();"],
				["COUNTER\tcurrent value of the countdown or countup", "COUNTER(${1:<id>});"],
				["SECTOTIME\tformats the amount of seconds to time", "&${1:time} = SECTOTIME(${2:<seconds>},${3:[format]});"],
				["GETCHESTNAME\treturns the name of the open chest", "&${1:name} = GETCHESTNAME();"],
				["GETEMPTYSLOTS\treturns empty slots in inventory", "#${1:slots} = GETEMPTYSLOTS(${2:[include non full slots]});"],
				["GETMOUSEITEM\tgets info about the held item", "${2:&${1:[id]} = }GETMOUSEITEM(&${1:[id]},#${3:[stacksizevar]},#${4:[datavar]},&${5:[nbt]});"],
				["GETSLOTITEMINV\tgets information about the item in the specified slot", "${2:[&${1:<id>}] = }GETSLOTITEMINV(${3:<slotid>},&${1:<id>},#${4:[stacksizevar]},#${5:[datavar]},&${6:[nbt]});"],
				["GETSLOTINV\tgets slot containing item in inventory", "#${1:[slot]} = GETSLOTINV(${2:<item>}:${3:[damage]},#${4:<idvar>},${5:[startfromslotid]});"],
				["IFINVISFULL\tChecks if inventory is full", "IFINVISFULL(${1:[item]});\n	$2\nENDIF;\n$3"],
				["IFININV\tChecks whether itemtypes are in the inventory", "IFININV(${1:[mode]},${2:<items>});\n	$3\nENDIF;\n$4"],
				["IFENCHANTED\tChecks if the item is enchanted", "IFENCHANTED(${1:<slot>},&${2:[item]},#${3:[stacksize]},#${4:[datavar]},&${5:[nbt]});\n	$6\nENDIF;\n$7"],
				["SETSLOTITEM\tset the contents of a hotbar slot", "SETSLOTITEM(${1:<item>}:${2:[damage]}${3:,<slot>},${4:[amount]},${5:[nbt]});"],
				["GETFISHHOOK\tget the x, y and z (3dp) of the bobber", "${2:#${1:[ytotal]} = }GETFISHHOOK(#${3:[x]},#${4:[xprecision]},#${5:[y]},#${6:[yprecision]},#${7:[z]},#${8:[zprecision]});"],
				["MAP", "#${1:result} = MAP(${2:<x>},${3:<minfrom>},${4:<maxfrom>},${5:<minto>},${6:<maxto>})"],
				["PARTICLE\tSpawns particles similar to the vanilla command", "${2:&${1:errors}[] = }PARTICLE(${3:<particlename>},${4:<x>},${5:<y>},${6:<z>},${7:<dx>},${8:<dy>},${9:<dz>},${10:[count]},${11:[mode]})"],
				["COUNTITEM\tAmount of items in your current inventory", "#${1:count} = COUNTITEM(${2:<item>}:${3:[damage]})"],
				["COUNTITEMINV\tAmount of items in your survival inventory", "#${1:count} = COUNTITEMINV(${2:<item>}:${3:[damage]})"],
				["CREATECONTROL\tCreates a control on the specified screen at row and column position", "${2:[&${1:controlname}] = }CREATECONTROL(${3:<screenname|layouts|types>},${4:[element type]},${5:[row]},${6:[column]});"],
				["TIMESTAMPTODATE\tFormat a timestamp in seconds", "&${1:date} = TIMESTAMPTODATE(${2:<timestamp>},${3:[in milliseconds|date format]},${4:[in milliseconds]});"],
				["STOP\tStops macro matching regex or array", "STOP(${1:[array|regex]});"],
				["KLACAIBAVERSION\tReturns the version of klacaiba (major * 100000 + minor * 1000 + patch)", "%KLACAIBAVERSION%"],
				["STRLEN\tReturns the length of the string or 0 if none is present", "#${1:length} = STRLEN(${2:<string>});"],
				["GETBREAKSPEED\tReturns the amount of time required to break a block or 0 if infinite of none specified", "#${1:ticks} = GETBREAKSPEED(${2:<blockid>});"],
				["IFCANHARVESTBLOCK\tChecks if the block of &blockid can currently be harvested", "IFCANHARVESTBLOCK(${1:<blockid>});\n	$2\nENDIF;\n$3"],
				["POLLEVENT\tOpens a stack with an infinite iterator for a specific event", "POLLEVENT(${1:[event]});\n	$3\n	AWAIT;\nNEXT;\n$4"],
				["POLLALL\tList all variables of the event", "%POLLALL%"],
				["AWAIT\tShould be placed above the closing next of a pollevent", "AWAIT;"],

				["DELETECONTROL\tDeletes a control by name from any gui", "DELETECONTROL(${1:<controlname>});"],
				["NOTIFY\tcreates a system tray", "NOTIFY(${1:[title]},${2:[message]});"],
				["GETSLOTITEMEXT\t+ argument for the itemname of item", "${2:&${1:[itemid]} = }GETSLOTITEMEXT(#${3:<slotid>},&${1:[itemid]},${4:[stacksize]},${5:[damage]},${6:[itemname]});"],
				["GETSLOTITEMNBT\t+ argument for the nbt of item", "${2:&${1:[itemid]} = }GETSLOTITEMNBT(#${3:<slotid>},${1:[itemid]},${4:[stacksize]},${5:[damage]},${6:[nbt]});"],
				["GETSLOTITEMENCHANTS\t+ argument for enchantments", "${2:&${1:[itemid]} = }GETSLOTITEMENCHANTS(#${3:<slotid>},${1:[itemid]},${4:[stacksize]},${5:[damage]},${6:[enchants]});"],
				["ISBOOLEAN\tchecks if the value is a boolean", "${2:[${1:bool}] = }ISBOOLEAN(${3:<string>},${1:[bool]});"],
				["ISFLOAT\tchecks if the value is a float", "${2:${1:[bool]} = }ISFLOAT(${3:<string>},${1:[bool]});"],
				["ISINTEGER\tchecks if the value is an integer", "${2:${1:[bool]} = }ISINTEGER(${3:<string>},${1:[bool]});"],
				["ISJSONARRAY\tchecks if the value is a json array", "${2:${1:[bool]} = }ISJSONARRAY(${3:<string>},${1:[bool]});"],
				["ISJSONOBJECT\tchecks if the value is a json object", "${2:${1:[bool]} = }ISJSONOBJECT(${3:<string>},${1:[bool]});"],
				["ISJSONPRIMITIVE\tchecks if value isjson primitive", "${2:${1:[bool]} = }ISJSONPRIMITIVE(${3:<string>}${1:,[bool}]);"],
				["ISNUMBER\tchecks if the value is a number", "${2:${1:[bool]} = }ISNUMBER(${3:<string>},${1:[bool]});"],
				["ISSTRING\tchecks if the value is a string", "${2:${1:[bool]} = }ISSTRING(${3:<string>},${1:[bool]});"],
				["JSONADD\tadds key and value to the json", "${2:&${1:[output]} = }JSONADD(${3:<json>},${4:<key>},${5:<value>},&${1:[output]});"],
				["JSONGET\tgets value of a key", "${2:&${1:[output]} = }JSONGET(${3:<json>},${4:<key>},&${1:[output]});"],
				["JSONHAS\treturns if the json contains the key", "${2:${1:[bool]} = }JSONHAS(${3:<json>},${4:<key>},${1:[bool]});"],
				["JSONREMOVE\tremoves a key-value-pair from the json", "${2:&${1:[output]} = }JSONREMOVE(${3:<json>},${4:<key>},&${1:[output]});"],
				["GETJSONKEYS\treturns list of all keys of the json", "${2:&${1:[keys]} = }GETJSONKEYS(${3:<json>},&${1:[keys]}[]);"],
				["GETJSONARRAY\treturns json as key:value array", "${2:&${1:[array]} = }GETJSONASARRAY(${3:<json>},${1:[array]}[]));"],
				["JSONARRAYADD\tadds an element to the json array", "${2:&${1:[jsonarray]} = }JSONARRAYADD(${3:<jsonarray>},${4:<element>},&${1:[jsonarray]});"],
				["JSONARRAYGET\treturns the element of the jsonarray", "${2:&${1:[output]} = }JSONARRAYGET(${3:<jsonarray>},${4:<index>},&${1:[output]});"],
				["JSONARRAYSIZE\treturns the size of the jsonarray", "${2:#${1:[size]} = }JSONARRAYSIZE(${3:<jsonarray>},#${1:[size]});"],
				["GETCLIPBOARD\treturns content of clipboard", "GETCLIPBOARD(&${1:[text]});"],
				["SETCLIPBOARD\tsets the clipboard text", "SETCLIPBOARD(${1:<text>});"],
				["HTTPGET\thttpget request to url", "${2:&${1:[response]}[] = }HTTPGET(${3:<url>},${4:<query>},${5:<#status>},&${1:[response]});"],
				["HTTPPOST\thttppost request to url with data", "${2:&${1:[response]}[] = }HTTPPOST(${3:<url>},${4:<data>},${5:<#status>},&${1:[response]});"],
				["HTTPPUT\thttpput request to url with data", "${2:&${1:[response]}[] = }HTTPPUT(${3:<url>},${4:<data>},${5:<#status>},&${1:[response]});"],
				["HTTPDELETE\trequest to specified url", "${2:&${1:[response]}[] = }HTTPDELETE(${3:<url>},${4:<query>},${5:<#status>},&${1:[response]});"],
				["URLENCODE\turl encodes the string", "${2:&${1:[output]} = }URLENCODE(${3:<string>},&${1:[output]});"],
				["SETREQUESTHEADER\tsets header for next request", "SETREQUESTHEADER(&${1:<field>},&${2:<value>});"],
				["GETHITSIGNTEXT\treturns signtext of hit sign", "${2:&${1:[outarray]}[] = }GETHITSIGNTEXT(&${1:[outarray]}[]);"],
				["GETSIGNTEXT\treturns signtext at coordinates", "${2:&${1:[outarray]} = }GETSIGNTEXT(${3:<x>},${4:<y>},${5:<z>},&${1:[outarray]});"],
				["SETSIGNTEXT\tset text of sign in SP", "SETSIGNTEXT(${1:<x>},${2:<y>}${3:,<z>},${4:<line1>},${5:<line2>},${6:<line3>},${7:<line4>});"],

				["TEAMS\tIterates over all teams", "teams"],
				["OBJECTIVES\tIterates over all objectives", "objectives"],
				["SCORE\tIterates over all scores", "score"],
				["ACTIONS\tIterates over all actions", "actions"],
				["EVENTS\tIterates over all events", "events"],
				["ITERATORS\tIterates over all iterators", "iterators"],
				["INVENTORY\tIterates over your inventory", "inventory"],

				["SLOTINDEX\t(inventory iterator)", "%SLOTINDEX%"],
				["SLOTID\t(inventory iterator)", "%SLOTID%"],
				["SLOTSTACKSIZE\t(inventory iterator)", "%SLOTSTACKSIZE%"],
				["SLOTDATAVAR\t(inventory iterator)", "%SLOTDATAVAR%"],
				["SLOTTAG\t(inventory iterator)", "%SLOTTAG%"],

				["PLAYERUUID\t(players iterator) UUID of the player with dashes", "%PLAYERUUID%"],
				["PLAYERDISPLAYNAME\t(players iterator) Displayname of the player", "%PLAYERDISPLAYNAME%"],
				["PLAYERTEAM\t(players iterator) Scoreboard team of the player as JSON", "%PLAYERTEAM%"],
				["PLAYERPING\t(players iterator) Ping of the player", "%PLAYERPING%"],
				["PLAYERISLEGACY\t(players iterator) Whether the player uses a legacy account", "%PLAYERISLEGACY%"],

				["TEAMALLOWFRIENDLYFIRE\t(teams iterator) If the team allows friendly fire", "%TEAMALLOWFRIENDLYFIRE%"],
				["TEAMCOLLISIONRULE\t(teams iterator) Collisionrule of the team", "%TEAMCOLLISIONRULE%"],
				["TEAMCOLOR\t(teams iterator) Color of the team", "%TEAMCOLOR%"],
				["TEAMDEATHMESSAGEVISIBILITY\t(teams iterator) Deathmessage visibility ruleing of the team", "%TEAMDEATHMESSAGEVISIBILITY%"],
				["TEAMDISPLAYNAME\t(teams iterator) Displayname of the team", "%TEAMDISPLAYNAME%"],
				["TEAMNAME\t(teams iterator) Name of the team", "%TEAMNAME%"],
				["TEAMNAMETAGVISIBILITY\t(teams iterator) Nametag visibility of the team", "%TEAMNAMETAGVISIBILITY%"],
				["TEAMSEEFRIENDLYINVISIBLES\t(teams iterator) Whether the team can see friendly invisibles", "%TEAMSEEFRIENDLYINVISIBLES%"],
				["TEAMPREFIX\t(teams iterator) Prefix of the team", "%TEAMPREFIX%"],
				["TEAMSUFFIX\t(teams iterator) Suffix of the team", "%TEAMSUFFIX%"],
				["TEAMMEMBERS\t(teams iterator) Membernames of the team", "%TEAMMEMBERS%"],

				["OBJECTIVECRITERIA\t(objectives iterator) Criteria of the objective", "%OBJECTIVECRITERIA%"],
				["OBJECTIVEDISPLAYNAME\t(objectives iterator) Displayname of the objective", "%OBJECTIVEDISPLAYNAME%"],
				["OBJECTIVENAME\t(objectives iterator) Name of the objective", "%OBJECTIVENAME%"],
				["OBJECTIVERENDERTYPE\t(objectives iterator) Rendertype of the objective", "%OBJECTIVERENDERTYPE%"],

				["SCOREOBJECTIVENAME\t(scores iterator) Name of the associated objective", "%SCOREOBJECTIVENAME%"],
				["SCOREPLAYERNAME\t(scores iterator) Name of the owning player", "%SCOREPLAYERNAME%"],
				["SCOREVALUE\t(scores iterator) Value of the score", "%SCOREVALUE%"],

				["LATENCY\tPing of the player to the server", "%LATENCY%"],
				["HACKED\tWhether all the functions of the module have been applied to the client", "%HACKED%"],
				["MINECRAFTDIR\tFilepath of the current minecraft directory", "%MINECRAFTDIR%"],
				["MACROSCONFIGDIR\t%MINECRAFTDIR%/.liteconfig/common/macros", "%MACROSCONFIGDIR%"],
				["FILESEPERATOR\tDefault path seperator used by the system", "%FILESEPERATOR%"],
				["MODULENEI\tReturns true if the module is installed", "%MODULENEI%"],
				["MODULEHTTP\tReturns true if the module is installed", "%MODULEHTTP%"],
				["MODULEJSON\tReturns true if the module is installed", "%MODULEJSON%"],
				["MODULESIGNTEXT\tReturns true if the module is installed", "%MODULESIGNTEXT%"],
				["MODULECLIPBOARD\tReturns true if the module is installed", "%MODULECLIPBOARD%"],
				["MODULEAEI\tReturns true if the module is installed", "%MODULEAEI%"],
				["ACTIONNAME\t(actions iterator) Action name", "%ACTIONNAME%"],
				["ACTIONUSAGE\t(actions iterator) Action usage", "%ACTIONUSAGE%"],
				["ACTIONRETURN\t(actions iterator) Action return", "%ACTIONRETURN%"],
				["ACTIONDESCRIPTION\t(actions iterator) Action description", "%ACTIONDESCRIPTION%"],
				["NEWEFFECT\t(onPotionEffect) New potion effect", "%NEWEFFECT%"],
				["NEWEFFECTID\t(onPotionEffect) New potion effect id", "%NEWEFFECTID%"],
				["NEWEFFECTNAME\t(onPotionEffect) New potion effect name", "%NEWEFFECTNAME%"],
				["NEWEFFECTPOWER\t(onPotionEffect) New potion effect power", "%NEWEFFECTPOWER%"],
				["NEWEFFECTTIME\t(onPotionEffect) New potion effect time", "%NEWEFFECTTIME%"],
				["ITERATORNAME\t(iterators iterator) Iterator name", "%ITERATORNAME%"],
				["EVENTNAME\t(events iterator) Event name", "%EVENTNAME%"],
				["EVENTID\t(events iterator) Event id", "%EVENTID%"],
				["EVENTHELP[]\t(events iterator) Event help", "%EVENTHELP%"],
				["ACTIONNAME\t(actions iterator) Action name", "%ACTIONNAME%"],
				["ACTIONUSAGE\t(actions iterator) Action usuage", "%ACTIONUSAGE%"],
				["ACTIONRETURN\t(actions iterator) Action return", "%ACTIONRETURN%"],
				["ACTIONDESCRIPTION\t(actions iterator) Action description", "%ACTIONDESCRIPTION%"],

				["TRADES\tIterates over all trades", "trades"],
				["TRADEBUYITEM\t(trades iterator)", "%TRADEBUYITEM%"],
				["TRADEBUYITEMAMOUNT\t(trades iterator)", "%TRADEBUYITEMAMOUNT%"],
				["TRADEBUYITEM2\t(trades iterator)", "%TRADEBUYITEM2%"],
				["TRADEBUYITEM2AMOUNT\t(trades iterator)", "%TRADEBUYITEM2AMOUNT%"],
				["TRADESELLITEM\t(trades iterator)", "%TRADESELLITEM%"],
				["TRADESELLITEMAMOUNT\t(trades iterator)", "%TRADESELLITEMAMOUNT%"],
				["TRADEUSES\t(trades iterator)", "%TRADEUSES%"],
				["TRADEMAXUSES\t(trades iterator)", "%TRADEMAXUSES%"],

				["FARHIT\tExtended reach %HIT%", "%FARHIT%"],
				["FARHITID\tExtended reach %HITID%", "%FARHITID%"],
				["FARHITDATA\tExtended reach %HITDATA%", "%FARHITDATA%"],
				["FARHITNAME\tExtended reach %HITNAME%", "%FARHITNAME%"],
				["FARHITSIDE\tExtended reach %HITSIDE%", "%FARHITSIDE%"],
				["FARHITX\tExtended reach %HITX%", "%FARHITX%"],
				["FARHITY\tExtended reach %HITY%", "%FARHITY%"],
				["FARHITZ\tExtended reach %HITZ%", "%FARHITZ%"],
				["FARHITUUID\tExtended reach %HITUUID%", "%FARHITUUID%"],
				["FARHITDIST\tExtended reach %HITDIST%", "%FARHITDIST%"],
				["MODULEFARHIT\tReturns true if the module is installed", "%MODULEFARHIT%"],

				["SOUNDXPOSF\t(onSound) XPOS of sound as float", "%SOUNDXPOSF%"],
				["SOUNDYPOSF\t(onSound) YPOS of sound as float", "%SOUNDYPOSF%"],
				["SOUNDZPOSF\t(onSound) ZPOS of sound as float", "%SOUNDZPOSF%"],
				["SOUNDXPOS\t(onSound) XPOS of sound as int", "%SOUNDXPOS%"],
				["SOUNDYPOS\t(onSound) YPOS of sound as int", "%SOUNDYPOS%"],
				["SOUNDZPOS\t(onSound) ZPOS of sound as int", "%SOUNDZPOS%"],
				["SOUNDCANREPEAT\t(onSound) Whether the sound is able to repeat", "%SOUNDCANREPEAT%"],
				["SOUNDATTENUATIONTYPE\t(onSound) Type of attenuation", "%SOUNDATTENUATIONTYPE%"],
				["SOUNDCATEGORY\t(onSound) Category of sound", "%SOUNDCATEGORY%"],
				["SOUNDPITCH\t(onSound) Pitch of the sound as float", "%SOUNDPITCH%"],
				["SOUNDVOLUME\t(onSound) Volume of the sound as float", "%SOUNDVOLUME%"],
				["SOUNDRESOURCE\t(onSound) Resourcepath of the sound", "%SOUNDRESOURCE%"],

				["ENTITYTYPE\t(entities iterator) Type of the entity", "%ENTITYTYPE%"],
				["ENTITYNAME\t(entities iterator) Name of the entity", "%ENTITYNAME%"],
				["ENTITYUUID\t(entities iterator) UUID of the entity", "%ENTITYUUID%"],
				["ENTITYXPOSF\t(entities iterator) X coordinates of the entity as float", "%ENTITYXPOSF%"],
				["ENTITYYPOSF\t(entities iterator) Y coordinates of the entity as float", "%ENTITYYPOSF%"],
				["ENTITYZPOSF\t(entities iterator) Z coordinates of the entity as float", "%ENTITYZPOSF%"],
				["ENTITYXPOS\t(entities iterator) X coordinates of the entity as integer", "%ENTITYXPOS%"],
				["ENTITYYPOS\t(entities iterator) Y coordinates of the entity as integer", "%ENTITYYPOS%"],
				["ENTITYZPOS\t(entities iterator) Z coordinates of the entity as integer", "%ENTITYZPOS%"],
				["ENTITYTAG\t(entities iterator) Tag of the entity", "%ENTITYTAG%"],
				["ENTITYDX\t(entities iterator) X difference between the player and the entity", "%ENTITYDX%"],
				["ENTITYDY\t(entities iterator) Y difference between the player and the entity", "%ENTITYDY%"],
				["ENTITYDZ\t(entities iterator) Z difference between the player and the entity", "%ENTITYDZ%"],
				["ENTITYDISTANCE\t(entities iterator) Distance between the player and the entity", "%ENTITYDISTANCE%"],
				["ENTITYPITCHFROMPLAYER\t(entities iterator) Pitch from the player to entity", "%ENTITYPITCHFROMPLAYER%"],
				["ENTITYYAWFROMPLAYER\t(entities iterator) Yaw from the player to entity", "%ENTITYYAWFROMPLAYER%"],
				["ENTITYNBT\t(entities iterator) NBT of the entity", "%ENTITYNBT%"],
				["ENTITYNBTKEYS\t(entities iterator) Array of the keys of the NBT of the entity", "%ENTITYNBTKEYS%"],
				["ENTITYNBT<key>\t(entities iterator) Quick way to access value of a specififc key", "%ENTITYNBT${1:<key>}%"],
				["ENTITYDIR\t(entities iterator) Fuzzy direction in which the entity is", "%ENTITYDIR%"],
				["ENTITYPITCH\t(entities iterator) Pitch where the entity is looking at", "%ENTITYPITCH%"],
				["ENTITYYAW\t(entities iterator) Yaw where the entity is looking at", "%ENTITYYAW%"],
				["ENTITYHEALTH\t(entities iterator) Health of the entity", "%ENTITYHEALTH%"],
				["ENTITYMAXHEALTH\t(entities iterator) Max health of the entity", "%ENTITYMAXHEALTH%"],
				["ENTITYISITEM\t(entities iterator) True if it's an dropped item", "%ENTITYISITEM%"],
				["ENTITYITEMAGE\t(entities iterator) Age of the dropped item", "%ENTITYITEMAGE%"],
				["ENTITYITEMOWNER\t(entities iterator) Owner of the dropped item", "%ENTITYITEMOWNER%"],
				["ENTITYITEMTHROWER\t(entities iterator) Thrower of the dropped item", "%ENTITYITEMTHROWER%"],
				["ENTITYITEMNAME\t(entities iterator) Localized name of the dropped item", "%ENTITYITEMTHROWER%"],
				["ENTITYITEMUNLOCALIZEDNAME\t(entities iterator) Unlocalized name of the dropped item", "%ENTITYITEMUNLOCALIZEDNAME%"],
				["ENTITYITEMCOUNT\t(entities iterator) Amount of the dropped item", "%ENTITYITEMCOUNT%"],
				["ENTITYITEMDISPLAYNAME\t(entities iterator) Displayname of the dropped item", "%ENTITYITEMDISPLAYNAME%"],
				["ENTITYITEMDAMAGE\t(entities iterator) Damage of the dropped item", "%ENTITYITEMDAMAGE%"],
				["ENTITYITEMMAXDAMAGE\t(entities iterator) Max damage of the dropped item", "%ENTITYITEMMAXDAMAGE%"],
				["ENTITYITEMMETADATA\t(entities iterator) Metadata of the dropped item", "%ENTITYITEMMETADATA%"],
				["ENTITYITEMENCHANTED\t(entities iterator) True if the dropped item is enchanted", "%ENTITYITEMENCHANTED%"],
				["ENTITYITEMSTACKABLE\t(entities iterator) True if the dropped item is stackable", "%ENTITYITEMSTACKABLE%"],
				["ENTITYMAINHANDNAME\t(entities iterator) Name of the mainhand item", "%ENTITYMAINHANDNAME%"],
				["ENTITYMAINHANDID\t(entities iterator) ID of the mainhand item", "%ENTITYMAINHANDID%"],
				["ENTITYMAINHANDNID\t(entities iterator) Numerical ID of the mainhand item", "%ENTITYMAINHANDNID%"],
				["ENTITYMAINHANDDAMAGE\t(entities iterator) Damage of the mainhand item", "%ENTITYMAINHANDDAMAGE%"],
				["ENTITYMAINHANDCOUNT\t(entities iterator) Amount of the mainhand item", "%ENTITYMAINHANDCOUNT%"],
				["ENTITYMAINHANDENCHANTMENTS\t(entities iterator) Enchantments of the mainhand item", "%ENTITYMAINHANDENCHANTMENTS%"],
				["ENTITYOFFHANDNAME\t(entities iterator) Name of the offhand item", "%ENTITYOFFHANDNAME%"],
				["ENTITYOFFHANDID\t(entities iterator) ID of the offhand item", "%ENTITYOFFHANDID%"],
				["ENTITYOFFHANDNID\t(entities iterator) Numerical ID of the offhand item", "%ENTITYOFFHANDNID%"],
				["ENTITYOFFHANDDAMAGE\t(entities iterator) Damage of the offhand item", "%ENTITYOFFHANDDAMAGE%"],
				["ENTITYOFFHANDCOUNT\t(entities iterator) Amount of the offhand item", "%ENTITYOFFHANDCOUNT%"],
				["ENTITYOFFHANDENCHANTMENTS\t(entities iterator) Enchantments of the offhand item", "%ENTITYOFFHANDENCHANTMENTS%"],
				["ENTITYBOOTSNAME\t(entities iterator) Name of the boots item", "%ENTITYBOOTSNAME%"],
				["ENTITYBOOTSID\t(entities iterator) ID of the boots item", "%ENTITYBOOTSID%"],
				["ENTITYBOOTSNID\t(entities iterator) Numerical ID of the boots item", "%ENTITYBOOTSNID%"],
				["ENTITYBOOTSDAMAGE\t(entities iterator) Damage of the boots item", "%ENTITYBOOTSDAMAGE%"],
				["ENTITYBOOTSCOUNT\t(entities iterator) Amount of the boots item", "%ENTITYBOOTSCOUNT%"],
				["ENTITYBOOTSENCHANTMENTS\t(entities iterator) Enchantments of the boots item", "%ENTITYBOOTSENCHANTMENTS%"],
				["ENTITYLEGGINGSNAME\t(entities iterator) Name of the leggings item", "%ENTITYLEGGINGSNAME%"],
				["ENTITYLEGGINGSID\t(entities iterator) ID of the leggings item", "%ENTITYLEGGINGSID%"],
				["ENTITYLEGGINGSNID\t(entities iterator) Numerical ID of the leggings item", "%ENTITYLEGGINGSNID%"],
				["ENTITYLEGGINGSDAMAGE\t(entities iterator) Damage of the leggings item", "%ENTITYLEGGINGSDAMAGE%"],
				["ENTITYLEGGINGSCOUNT\t(entities iterator) Amount of the leggings item", "%ENTITYLEGGINGSCOUNT%"],
				["ENTITYLEGGINGSENCHANTMENTS\t(entities iterator) Enchantments of the leggings item", "%ENTITYLEGGINGSENCHANTMENTS%"],
				["ENTITYCHESTPLATENAME\t(entities iterator) Name of the chestplate item", "%ENTITYCHESTPLATENAME%"],
				["ENTITYCHESTPLATEID\t(entities iterator) ID of the chestplate item", "%ENTITYCHESTPLATEID%"],
				["ENTITYCHESTPLATENID\t(entities iterator) Numerical ID of the chestplate item", "%ENTITYCHESTPLATENID%"],
				["ENTITYCHESTPLATEDAMAGE\t(entities iterator) Damage of the chestplate item", "%ENTITYCHESTPLATEDAMAGE%"],
				["ENTITYCHESTPLATECOUNT\t(entities iterator) Amount of the chestplate item", "%ENTITYCHESTPLATECOUNT%"],
				["ENTITYCHESTPLATEENCHANTMENTS\t(entities iterator) Enchantments of the chestplate item", "%ENTITYCHESTPLATEENCHANTMENTS%"],
				["ENTITYHELMETNAME\t(entities iterator) Name of the helmet item", "%ENTITYHELMETNAME%"],
				["ENTITYHELMETID\t(entities iterator) ID of the helmet item", "%ENTITYHELMETID%"],
				["ENTITYHELMETNID\t(entities iterator) Numerical ID of the helmet item", "%ENTITYHELMETNID%"],
				["ENTITYHELMETDAMAGE\t(entities iterator) Damage of the helmet item", "%ENTITYHELMETDAMAGE%"],
				["ENTITYHELMETCOUNT\t(entities iterator) Amount of the helmet item", "%ENTITYHELMETCOUNT%"],
				["ENTITYHELMETENCHANTMENTS\t(entities iterator) Enchantments of the helmet item", "%ENTITYHELMETENCHANTMENTS%"],
				["EHITX\tX value of entity your're looking at or 0 if not looking at an entity", "%EHITX%"],
				["EHITZ\tZ value of entity your're looking at or 0 if not looking at an entity", "%EHITZ%"],
				["EHITY\tY value of entity your're looking at or 0 if not looking at an entity", "%EHITY%"],

				["GETDENSITY\tSearches for sugarcane in the given direction", "GETDENSITY(${1:[N/E/S/W]},#${2:<limit_search>},&${3:<initial_position>},#${4:<blocks_searched>},#${5:<sugarcane_found>});"],
				["GETITEMSTACKSIZE\tSearches the inventory, returns the stacksize", "#${1:stacksize} = GETITEMSTACKSIZE(&${2:<item_name>},#${3:[limit_search]});"],
				["GETPERCENTAGE\tDoes first divided by second times 100", "GETPERCENTAGE(#${1:[percentage]},#${2:<first>},#${3:<second>});"],
				["GETSLOTPOSITIONS\tSearches the inventory, returns the position", "GETSLOTPOSITIONS(&${1:<item_name>},#${2:<result_position>},#${3:[result_stacksize]});"],

				["GETSLOTNBT\tGet nbt of item in slot", "GETSLOTNBT(${1:<slotid>},${2:<path>},&${3:[itemId]},#${4:[stackSize]},#${5:[damage]});"],
				["PRESSBUTTON\tPress button", "PRESSBUTTON(${1:<buttonid>},${2:[button]});"],
				["GETPROP\tgets property of block at coordinates", "GETPROP(${1:<x>},${2:<y>},${3:<z>},${4:<propname>},#${5:[propvar]});"],
				["SLOTMIDDLECLICK\tmiddle click inventory slot", "SLOTMIDDLECLICK(${1:<slotid>});"],

				["MOD\tModulus function (Yaku)", "MOD(${1:<#divident>},${2:<#divisor>});"],
				["TRUNC\tReturns the integer part of the number", "TRUNC(${1:<#float>});"],
				["ACKERMANN\tAckermann function implementation", "ACKERMANN(${1:<#m>},${2:<#n>});"],
				["CALCSTACKS\tCalculates stacks", "CALCSTACKS(#${1:<items>},#${2:[stacks]},#${3:[leftovers]});"],
				["PICKMOD\tImproved original pick action", "PICKMOD(${1:[namespace]}:${2:<itemid>}:${3:[damage]},${4:[addInCreative]});"],
				["ANTIGHOST\tResolve ghost blocks issue", "ANTIGHOST;"],

				["RUN\tRuns the specified script from cloudscript", "RUN(${1:<cloudscript>});"],
				["ADDANIM\tAdd animation", "ADDANIM(&${1:<array>}[]);"],
				["EVENT\tUsed by cloudscript to run an event", "EVENT(${1:<projectId>});"],
				["CHAT\tOpen cloudchat", "CHAT;"],
				["GETKEYBIND\tGet the macro on that key", "GETKEYBIND(${1:<key>}, &${2:<outvar>});"],
				["SETKEYBIND\tSet a macro on that key", "SETKEYBIND(${1:<key>}, ${2:<some code>});"],
				["RETURN\tEnd a macro and return a value", "RETURN(${1:<anything>});"],
				["SENDMESSAGE\tSend a message on a websocket channel", "SENDMESSAGE(${1:<channel>},${2:<message>});"],
				["ENCRYPT\tEncrypt the variable content", "ENCRYPT(&${1:<var>},${2:<16charskey>});"],
				["DECRYPT\tDecrypt the variable content", "DECRYPT(&${1:<var>},${2:<16charskey>});"],
				["REMOVE\tRemove something from array", "REMOVE(&${1:<array>}[],&${2:<outvar>},${3:[pos]});"],

				["BARITONE\tRuns any baritone command", "BARITONE(${1:<command>});"],
				["GOTO\tPathfinds to specified coordinates", "GOTO(${1:<x>},${2:<y>},${3:<z>});"],
				["SETTING\tChanges baritone setting", "SETTING(${1:<settingname>},${2:<value>});"],
				["CANCEL\tCancels current process", "CANCEL();"],
				["PAUSE\tPauses current process", "PAUSE();"],
				["RESUME\tResumes current process", "RESUME();"],
				["MINE\tSearchs and mines provied block", "MINE(${1:<blockname>});"],
				["FARM\tFarms near by crops toggle replant", "FARM();"],
				["SELSTART\tSets pos1 of selection", "SELSTART(${1:<x>},${2:<y>},${3:<z>});"],
				["SELEND\tSets pos2 of selection", "SELEND(${1:<x>},${2:<y>},${3:<z>});"],
				["SELCLEAR\tClears selections", "SELCLEAR();"],
				["SELREPLACE\tReplace specified block with replacement block", "SELREPLACE(${1:<blocktoreplace>},${2:<replacementblock>});"],
				["MODULEBARITONE\t(baritone module)", "%MODULEBARITONE%"],
				["BARITONE\t(baritone module)", "%BARITONE%"],
				["PATHFINDING\t(baritone module)", "%PATHFINDING%"],
				["FARMING\t(baritone module)", "%FARMING%"],
				["MINING\t(baritone module)", "%MINING%"],
				["FOLLOWING\t(baritone module)", "%FOLLOWING%"],
				["BUILDING\t(baritone module)", "%BUILDING%"],
				["ALLOWBREAK\t(baritone module)", "%ALLOWBREAK%"],
				["ALLOWPLACE\t(baritone module)", "%ALLOWPLACE%"],
				["ALLOWSPRINT\t(baritone module)", "%ALLOWSPRINT%"],
				["ALLOWPARKOUR\t(baritone module)", "%ALLOWPARKOUR%"],
				["ALLOWINVENTORY\t(baritone module)", "%ALLOWINVENTORY%"],
				["ALLOWWALKONBOTTOMSLAB\t(baritone module)", "%ALLOWWALKONBOTTOMSLAB%"],
				["ALLOWWATERBUCKETFALL\t(baritone module)", "%ALLOWWATERBUCKETFALL%"],
				["BLOCKBREAKADDITIONALMENTPENALTY\t(baritone module)", "%BLOCKBREAKADDITIONALMENTPENALTY%"],
				["BLOCKPLACEMENTPENALTY\t(baritone module)", "%BLOCKPLACEMENTPENALTY%"],
				["BLOCKREACHDISTANCE\t(baritone module)", "%BLOCKREACHDISTANCE%"],
				["MAXFALLHEIGHTNOWATER\t(baritone module)", "%MAXFALLHEIGHTNOWATER%"],
				["FREELOOK\t(baritone module)", "%FREELOOK%"],
				["REPLANTCROPS\t(baritone module)", "%REPLANTCROPS%"],

				["getiteminfo\tGets information about the specified slot", "GETITEMINFO(${1:[slot]},&${2:<idvar>},#${3:<stacksize>},#${4:<datavar>},&${5:<display>},&${6:<lore>});"],
				["getguiname\tGets the display name of the current GUI", "GETGUINAME(&${1:[name]});"],
				["invfull\tReturns empty or full in the string defined", "INVFULL(&${1:[string}]);"],

				["MODULEANVIL\t(baritone module)", "%MODULEANVIL%"],
				["SETANVILTEXT\tset name to string", "SETANVILTEXT(${1:<string>});"],

				["ALT\t(Pressed at start)", "%~ALT%"],
				["CTRL\t(Pressed at start)", "%~CTRL%"],
				["KEY_0\t(Pressed at start)", "%~KEY_0%"],
				["KEY_1\t(Pressed at start)", "%~KEY_1%"],
				["KEY_2\t(Pressed at start)", "%~KEY_2%"],
				["KEY_3\t(Pressed at start)", "%~KEY_3%"],
				["KEY_4\t(Pressed at start)", "%~KEY_4%"],
				["KEY_5\t(Pressed at start)", "%~KEY_5%"],
				["KEY_6\t(Pressed at start)", "%~KEY_6%"],
				["KEY_7\t(Pressed at start)", "%~KEY_7%"],
				["KEY_8\t(Pressed at start)", "%~KEY_8%"],
				["KEY_9\t(Pressed at start)", "%~KEY_9%"],
				["KEY_A\t(Pressed at start)", "%~KEY_A%"],
				["KEY_ADD\t(Pressed at start)", "%~KEY_ADD%"],
				["KEY_APOSTROPHE\t(Pressed at start)", "%~KEY_APOSTROPHE%"],
				["KEY_APPS\t(Pressed at start)", "%~KEY_APPS%"],
				["KEY_AT\t(Pressed at start)", "%~KEY_AT%"],
				["KEY_AX\t(Pressed at start)", "%~KEY_AX%"],
				["KEY_B\t(Pressed at start)", "%~KEY_B%"],
				["KEY_BACK\t(Pressed at start)", "%~KEY_BACK%"],
				["KEY_BACKSLASH\t(Pressed at start)", "%~KEY_BACKSLASH%"],
				["KEY_C\t(Pressed at start)", "%~KEY_C%"],
				["KEY_CAPITAL\t(Pressed at start)", "%~KEY_CAPITAL%"],
				["KEY_CIRCUMFLEX\t(Pressed at start)", "%~KEY_CIRCUMFLEX%"],
				["KEY_CLEAR\t(Pressed at start)", "%~KEY_CLEAR%"],
				["KEY_COLON\t(Pressed at start)", "%~KEY_COLON%"],
				["KEY_COMMA\t(Pressed at start)", "%~KEY_COMMA%"],
				["KEY_CONVERT\t(Pressed at start)", "%~KEY_CONVERT%"],
				["KEY_D\t(Pressed at start)", "%~KEY_D%"],
				["KEY_DECIMAL\t(Pressed at start)", "%~KEY_DECIMAL%"],
				["KEY_DELETE\t(Pressed at start)", "%~KEY_DELETE%"],
				["KEY_DIVIDE\t(Pressed at start)", "%~KEY_DIVIDE%"],
				["KEY_DOWN\t(Pressed at start)", "%~KEY_DOWN%"],
				["KEY_E\t(Pressed at start)", "%~KEY_E%"],
				["KEY_END\t(Pressed at start)", "%~KEY_END%"],
				["KEY_EQUALS\t(Pressed at start)", "%~KEY_EQUALS%"],
				["KEY_ESCAPE\t(Pressed at start)", "%~KEY_ESCAPE%"],
				["KEY_F\t(Pressed at start)", "%~KEY_F%"],
				["KEY_F1\t(Pressed at start)", "%~KEY_F1%"],
				["KEY_F10\t(Pressed at start)", "%~KEY_F10%"],
				["KEY_F11\t(Pressed at start)", "%~KEY_F11%"],
				["KEY_F12\t(Pressed at start)", "%~KEY_F12%"],
				["KEY_F13\t(Pressed at start)", "%~KEY_F13%"],
				["KEY_F14\t(Pressed at start)", "%~KEY_F14%"],
				["KEY_F15\t(Pressed at start)", "%~KEY_F15%"],
				["KEY_F16\t(Pressed at start)", "%~KEY_F16%"],
				["KEY_F17\t(Pressed at start)", "%~KEY_F17%"],
				["KEY_F18\t(Pressed at start)", "%~KEY_F18%"],
				["KEY_F19\t(Pressed at start)", "%~KEY_F19%"],
				["KEY_F2\t(Pressed at start)", "%~KEY_F2%"],
				["KEY_F3\t(Pressed at start)", "%~KEY_F3%"],
				["KEY_F4\t(Pressed at start)", "%~KEY_F4%"],
				["KEY_F5\t(Pressed at start)", "%~KEY_F5%"],
				["KEY_F6\t(Pressed at start)", "%~KEY_F6%"],
				["KEY_F7\t(Pressed at start)", "%~KEY_F7%"],
				["KEY_F8\t(Pressed at start)", "%~KEY_F8%"],
				["KEY_F9\t(Pressed at start)", "%~KEY_F9%"],
				["KEY_FUNCTION\t(Pressed at start)", "%~KEY_FUNCTION%"],
				["KEY_G\t(Pressed at start)", "%~KEY_G%"],
				["KEY_GRAVE\t(Pressed at start)", "%~KEY_GRAVE%"],
				["KEY_H\t(Pressed at start)", "%~KEY_H%"],
				["KEY_HOME\t(Pressed at start)", "%~KEY_HOME%"],
				["KEY_I\t(Pressed at start)", "%~KEY_I%"],
				["KEY_INSERT\t(Pressed at start)", "%~KEY_INSERT%"],
				["KEY_J\t(Pressed at start)", "%~KEY_J%"],
				["KEY_K\t(Pressed at start)", "%~KEY_K%"],
				["KEY_KANA\t(Pressed at start)", "%~KEY_KANA%"],
				["KEY_KANJI\t(Pressed at start)", "%~KEY_KANJI%"],
				["KEY_L\t(Pressed at start)", "%~KEY_L%"],
				["KEY_LBRACKET\t(Pressed at start)", "%~KEY_LBRACKET%"],
				["KEY_LCONTROL\t(Pressed at start)", "%~KEY_LCONTROL%"],
				["KEY_LEFT\t(Pressed at start)", "%~KEY_LEFT%"],
				["KEY_LMENU\t(Pressed at start)", "%~KEY_LMENU%"],
				["KEY_LMETA\t(Pressed at start)", "%~KEY_LMETA%"],
				["KEY_LSHIFT\t(Pressed at start)", "%~KEY_LSHIFT%"],
				["KEY_M\t(Pressed at start)", "%~KEY_M%"],
				["KEY_MINUS\t(Pressed at start)", "%~KEY_MINUS%"],
				["KEY_MOUSE3\t(Pressed at start)", "%~KEY_MOUSE3%"],
				["KEY_MOUSE4\t(Pressed at start)", "%~KEY_MOUSE4%"],
				["KEY_MULTIPLY\t(Pressed at start)", "%~KEY_MULTIPLY%"],
				["KEY_N\t(Pressed at start)", "%~KEY_N%"],
				["KEY_NEXT\t(Pressed at start)", "%~KEY_NEXT%"],
				["KEY_NOCONVERT\t(Pressed at start)", "%~KEY_NOCONVERT%"],
				["KEY_NONE\t(Pressed at start)", "%~KEY_NONE%"],
				["KEY_NUMLOCK\t(Pressed at start)", "%~KEY_NUMLOCK%"],
				["KEY_NUMPAD0\t(Pressed at start)", "%~KEY_NUMPAD0%"],
				["KEY_NUMPAD1\t(Pressed at start)", "%~KEY_NUMPAD1%"],
				["KEY_NUMPAD2\t(Pressed at start)", "%~KEY_NUMPAD2%"],
				["KEY_NUMPAD3\t(Pressed at start)", "%~KEY_NUMPAD3%"],
				["KEY_NUMPAD4\t(Pressed at start)", "%~KEY_NUMPAD4%"],
				["KEY_NUMPAD5\t(Pressed at start)", "%~KEY_NUMPAD5%"],
				["KEY_NUMPAD6\t(Pressed at start)", "%~KEY_NUMPAD6%"],
				["KEY_NUMPAD7\t(Pressed at start)", "%~KEY_NUMPAD7%"],
				["KEY_NUMPAD8\t(Pressed at start)", "%~KEY_NUMPAD8%"],
				["KEY_NUMPAD9\t(Pressed at start)", "%~KEY_NUMPAD9%"],
				["KEY_NUMPADCOMMA\t(Pressed at start)", "%~KEY_NUMPADCOMMA%"],
				["KEY_NUMPADENTER\t(Pressed at start)", "%~KEY_NUMPADENTER%"],
				["KEY_NUMPADEQUALS\t(Pressed at start)", "%~KEY_NUMPADEQUALS%"],
				["KEY_O\t(Pressed at start)", "%~KEY_O%"],
				["KEY_P\t(Pressed at start)", "%~KEY_P%"],
				["KEY_PAUSE\t(Pressed at start)", "%~KEY_PAUSE%"],
				["KEY_PERIOD\t(Pressed at start)", "%~KEY_PERIOD%"],
				["KEY_POWER\t(Pressed at start)", "%~KEY_POWER%"],
				["KEY_PRIOR\t(Pressed at start)", "%~KEY_PRIOR%"],
				["KEY_Q\t(Pressed at start)", "%~KEY_Q%"],
				["KEY_R\t(Pressed at start)", "%~KEY_R%"],
				["KEY_RBRACKET\t(Pressed at start)", "%~KEY_RBRACKET%"],
				["KEY_RCONTROL\t(Pressed at start)", "%~KEY_RCONTROL%"],
				["KEY_RETURN\t(Pressed at start)", "%~KEY_RETURN%"],
				["KEY_RIGHT\t(Pressed at start)", "%~KEY_RIGHT%"],
				["KEY_RMENU\t(Pressed at start)", "%~KEY_RMENU%"],
				["KEY_RMETA\t(Pressed at start)", "%~KEY_RMETA%"],
				["KEY_RSHIFT\t(Pressed at start)", "%~KEY_RSHIFT%"],
				["KEY_S\t(Pressed at start)", "%~KEY_S%"],
				["KEY_SCROLL\t(Pressed at start)", "%~KEY_SCROLL%"],
				["KEY_SECTION\t(Pressed at start)", "%~KEY_SECTION%"],
				["KEY_SEMICOLON\t(Pressed at start)", "%~KEY_SEMICOLON%"],
				["KEY_SLASH\t(Pressed at start)", "%~KEY_SLASH%"],
				["KEY_SLEEP\t(Pressed at start)", "%~KEY_SLEEP%"],
				["KEY_SPACE\t(Pressed at start)", "%~KEY_SPACE%"],
				["KEY_STOP\t(Pressed at start)", "%~KEY_STOP%"],
				["KEY_SUBTRACT\t(Pressed at start)", "%~KEY_SUBTRACT%"],
				["KEY_SYSRQ\t(Pressed at start)", "%~KEY_SYSRQ%"],
				["KEY_T\t(Pressed at start)", "%~KEY_T%"],
				["KEY_TAB\t(Pressed at start)", "%~KEY_TAB%"],
				["KEY_U\t(Pressed at start)", "%~KEY_U%"],
				["KEY_UNDERLINE\t(Pressed at start)", "%~KEY_UNDERLINE%"],
				["KEY_UNLABELED\t(Pressed at start)", "%~KEY_UNLABELED%"],
				["KEY_UP\t(Pressed at start)", "%~KEY_UP%"],
				["KEY_V\t(Pressed at start)", "%~KEY_V%"],
				["KEY_W\t(Pressed at start)", "%~KEY_W%"],
				["KEY_X\t(Pressed at start)", "%~KEY_X%"],
				["KEY_Y\t(Pressed at start)", "%~KEY_Y%"],
				["KEY_YEN\t(Pressed at start)", "%~KEY_YEN%"],
				["KEY_Z\t(Pressed at start)", "%~KEY_Z%"],
				["LMOUSE\t(Pressed at start)", "%~LMOUSE%"],
				["MIDDLEMOUSE\t(Pressed at start)", "%~MIDDLEMOUSE%"],
				["RMOUSE\t(Pressed at start)", "%~RMOUSE%"],
				["SHIFT\t(Pressed at start)", "%~SHIFT%"],
				["ACHIEVEMENTGET\tDisplays a popup you get when completing an advancement with a custom message and optionally a custom item", "ACHIEVEMENTGET(${1:<text>},${2:[itemid]}:${3:[damage]});"],
				["ALT", "%ALT%"],
				["AMBIENTVOLUME\tVolume level for Ambient/Environment", "%AMBIENTVOLUME%"],
				["ARMOUR\tArmour points (each icon equals 2 points)", "%ARMOUR%"],
				["ARRAYSIZE\tStores the size of the specified array in #outvar", "ARRAYSIZE(${1:<array>}[],#${2:[outvar]});"],
				["ASSIGN\tInternal function", "<var> = <value>;"],
				["ATTACKPOWER\tAttack power", "%ATTACKPOWER%"],
				["ATTACKSPEED\tAttack speed", "%ATTACKSPEED%"],
				["BIND\tSet the specified key binding to the specified key code", "BIND(${1:<bind>},${2:<keycode>});"],
				["BINDGUI\tBinds the specified custom screen to the slot specified", "BINDGUI(${1:<slot>},${2:<screen>});"],
				["BIOME\tBiome the Player is currently in", "%BIOME%"],
				["BLOCKVOLUME\tVolume level for Blocks", "%BLOCKVOLUME%"],
				["BOOTSDAMAGE\tMaximum uses of the Players boots", "%BOOTSDAMAGE%"],
				["BOOTSDURABILITY\tDurability of the Players boots", "%BOOTSDURABILITY%"],
				["BOOTSID\tID of the Players boots", "%BOOTSID%"],
				["BOOTSNAME\tDisplayname of the Players boots", "%BOOTSNAME%"],
				["BOWCHARGE", "%BOWCHARGE%"],
				["BREAK\tInterrupts exection of the innermost loop", "BREAK;"],
				["CALCYAWTO\tCalculates the absolute yaw angle", "CALCYAWTO(${1:<xpos>},${2:<zpos>},#${3:[yaw]},#${4:[dist}ance]);"],
				["CAMERA\tSet the current camera mode, call with no arguments to toggle modes", "CAMERA(${1:[mode]});"],
				["CAMERA\tCurrent camera mode", "%CAMERA%"],
				["CANFLY\tWhether the Player can fly", "%CANFLY%"],
				["CARDINALYAW\tYaw of the player relative to north (YAW + 180)", "%CARDINALYAW%"],
				["CHAT\t(onChat) Chat message with control codes", "%CHAT%"],
				["CHATCLEAN\t(onChat) Chat message without control codes", "%CHATCLEAN%"],
				["CHATFILTER\tEnable or disable the chat filter", "CHATFILTER(${1:<enabled>});"],
				["CHATHEIGHT\tSet height of the Minecraft chat whilst ingame", "CHATHEIGHT(${1:<value>},${2:[time]});"],
				["CHATHEIGHTFOCUSED\tSet height of the Minecraft chat whilst in the chat GUI", "CHATHEIGHTFOCUSED(${1:<value>},${2:[time]});"],
				["CHATJSON\t(onBetterChat) Chat message in JSON", "%CHATMESSAGE%"],
				["CHATMESSAGE\t(onChat) The message part of an incoming chat line, could be wrong", "%CHATMESSAGE%"],
				["CHATOPACITY\tSet opacity of the Minecraft chat", "CHATOPACITY(${1:<value>},${2:[time]});"],
				["CHATPLAYER\t(onChat) The player who send a chat line, could be wrong", "%CHATPLAYER%"],
				["CHATSCALE\tSet scale of the Minecraft chat", "CHATSCALE(${1:<value>},${2:[time]});"],
				["CHATVISIBLE\tSet visibility of minecraft chat", "CHATVISIBLE(${1:<value>});"],
				["CHATWIDTH\tSet width of the Minecraft chat", "CHATWIDTH(${1:<value}>,${2:[time]});"],
				["CHESTPLATEDAMAGE\tMaximum uses of the Players chestplate", "%CHESTPLATEDAMAGE%"],
				["CHESTPLATEDURABILITY\tDurability of the Players chestplate", "%CHESTPLATEDURABILITY%"],
				["CHESTPLATEID\tID of the Players chestplate", "%CHESTPLATEID%"],
				["CHESTPLATENAME\tDisplayname of the Players chestplate", "%CHESTPLATENAME%"],
				["CHUNKUPDATES\tAmount of chunk updates", "%CHUNKUPDATES%"],
				["CLEARCHAT\tClears all messages from the chat window", "CLEARCHAT();"],
				["CLEARCRAFTING\tCancels any queued crafting jobs", "CLEARCRAFTING();"],
				["CONFIG\tSwitch to the specified configuration", "CONFIG(${1:<configname>});"],
				["CONFIG\tLoaded config", "%CONFIG%"],
				["CONTAINERSLOTS\tAmount of slots in opened container", "%CONTAINERSLOTS%"],
				["CONTROLID\t(controls iterator) Internal id of the current control", "%CONTROLID%"],
				["CONTROLNAME\t(controls iterator) The name set in the control under Control Name", "%CONTROLNAME%"],
				["CONTROLS\tIterates over all existing controls", "CONTROLS([layout][:type])"],
				["CONTROLTYPE\t(controls iterator) Type of the current control", "%CONTROLTYPE%"],
				["COOLDOWN\tCooldown", "%COOLDOWN%"],
				["CRAFT\tQueues an auto-crafting request", "CRAFT(${1:<item>}:${2:[damage]},${3:[amount]},${4:[throw]},${5:[verbose]});"],
				["CRAFTANDWAIT\tQueues an auto-crafting request and waits", "CRAFTANDWAIT(${1:<item>}:${2:[damage]},${3:[amount]},${4:[throw]},${5:[verbose]});"],
				["CTRL", "%CTRL%"],
				["DATE\tCurrent date in the format year-month-day", "%DATE%"],
				["DATETIME\tCurrent date and time in the format year-month-day hour:minute:second", "%DATETIME%"],
				["DAY\tNumber of day", "%DAY%"],
				["DAYTICKS\tTICKS value modulo 24000 and shifted back 6000 so that 0 aligns with midnight ","%DAYTICKS%"],
				["DAYTIME\tIngame time in the format hh:mm", "%DAYTIME%"],
				["DEC\tDecrements the specified counter by 1 or by the specified amount", "DEC(#${1:<var>},${2:[amount]});"],
				["DECODE\tConverts an string from base64 back to an normal string", "DECODE(${1:<input>},${2:[&output]});"],
				["DIFFICULTY\tDifficulty of the world", "%DIFFICULTY%"],
				["DIMENSION\tDimension the Player is in", "%DIMENSION%"],
				["DIRECTION\tDirection the Player is looking at, shortened to the first character", "%DIRECTION%"],
				["DISCONNECT\tDisconnects from the current game or server", "DISCONNECT();"],
				["DISPLAYHEIGHT\tHeight of the minecraft window", "%DISPLAYHEIGHT%"],
				["DISPLAYNAME\tPlayer's displayname", "%DISPLAYNAME%"],
				["DISPLAYWIDTH\tWidth of the minecraft window", "%DISPLAYWIDTH%"],
				["DURABILITY\tDurability of the equipped item", "%DURABILITY%"],
				["ECHO\tSends the specified message to the server", "ECHO(${1:<text>});"],
				["EFFECT\t(effects iterator) Internal string id of the effect", "%EFFECT%"],
				["EFFECTID\t(effects iterator) Internal numeric id of the effect", "%EFFECTID%"],
				["EFFECTNAME\t(effects iterator) Display name of the effect", "%EFFECTNAME%"],
				["EFFECTPOWER\t(effects iterator) Power of the effect", "%EFFECTPOWER%"],
				["EFFECTS\tIterates over all currently applied effects", "effects"],
				["EFFECTTIME\t(effects iterator) Remaining time of the effect in seconds", "%EFFECTTIME%"],
				["ENCHANTMENT\t(enchantments iterator) Display name of the enchantment", "%ENCHANTMENT%"],
				["ENCHANTMENTNAME\t(enchantments iterator) Only the name of the enchantment", "%ENCHANTMENTNAME%"],
				["ENCHANTMENTPOWER\t(enchantments iterator) Power of the enchantment", "%ENCHANTMENTPOWER%"],
				["ENCHANTMENTS\tIterates over all enchantments on the equipped item", "enchantments"],
				["ENCODE\tConverts an string to base 64", "ENCODE(${1:<input>},&${2:[output]});"],
				["ENV\tIterates over all available variables", "env"],
				["EXEC\tCreates a task by running the specified script file", "EXEC(${1:<file.txt>},${2:[taskname]},${3:[params]});"],
				["EXPAND", "?% <variable>;"],
				["FILTER\tIndicate that this chat meesage should be filtered and terminate", "FILTER;"],
				["FLYING\tWhether the Player is flying", "%FLYING%"],
				["FOG\tToggles render distance, or optionally specify render distance", "FOG(${1:[value]});"],
				["FOV\tSets the FOV angle in degrees, specifying time causes the value to change smoothly", "FOV(${1:<value>},${2:[time]});"],
				["FOV\tField of View", "%FOV%"],
				["FPS\tFrames per Second", "%FPS%"],
				["GAMEMODE\tGamemode of the player as a string", "%GAMEMODE%"],
				["GAMMA\tSets the brightness value (percent), specifying time causes the value to change smoothly", "GAMMA(${1:<value>},${2:[time]});"],
				["GAMMA\tBrightness level", "%GAMMA%"],
				["GETID\tGets the ID and data value of the block at the specified coordinates", "GETID(${1:<x>},${2:<y>},${3:<z>},&${4:[idvar]},#${5:[datavar]},&${6:[variants]});"],
				["GETIDREL\tGets the ID and data value of the block at the specified coordinates relative to the player", "GETIDREL(${1:<xoffset>},${2:<yoffset>},${3:<zoffset>},&${4:[idvar]},#${5:[datavar]},&${6:[variants]});"],
				["GETITEMINFO\tGets the name and other info for the specified item id", "GETITEMINFO(${1:<item>}:${2:[damage]},&${3:[namevar]},#${4:[maxstacksize]},&${5:[type]},&${6:[dropid]});"],
				["GETPROPERTY\tReturns the value of the specified property from the specified GUI control", "GETPROPERTY(${1:<control>},${2:<property>});"],
				["GETSLOT\tGets the id of the slot containing an item matching the specified item id", "GETSLOT(${1:<item>}:${2:[damage]},#${3:<slotid>},${4:[startfromslotid]});"],
				["GETSLOTITEM\tGets information about the item in the specified slot", "GETSLOTITEM(${1:<slotid>},&${2:<idvar>},#${3:[stacksizevar]},#${4:[datavar]});"],
				["GUI\tOpens the specified gui screen", "GUI(${1:[name]});"],
				["GUI\tName of the currently open GUI", "%GUI%"],
				["HEALTH\tHealth points (each icon equals 2 points)", "%HEALTH%"],
				["HELMDAMAGE\tMaximum uses of the Players helm", "%HELMDAMAGE%"],
				["HELMDURABILITY\tDurability of the Players helm", "%HELMDURABILITY%"],
				["HELMID\tID of the Players helm", "%HELMID%"],
				["HELMNAME\tDisplayname of the Players helm", "%HELMNAME%"],
				["HIT\tType of the thing the Player is looking at", "%HIT%"],
				["HIT_AGE", "%HIT_AGE%"],
				["HIT_ATTACHED", "%HIT_ATTACHED%"],
				["HIT_AXIS", "%HIT_AXIS%"],
				["HIT_BITES", "%HIT_BITES%"],
				["HIT_CHECK_DECAY", "%HIT_CHECK_DECAY%"],
				["HIT_COLOR", "%HIT_COLOR%"],
				["HIT_CONDITIONAL", "%HIT_CONDITIONAL%"],
				["HIT_CONTENTS", "%HIT_CONTENTS%"],
				["HIT_DAMAGE", "%HIT_DAMAGE%"],
				["HIT_DECAYABLE", "%HIT_DECAYABLE%"],
				["HIT_DELAY", "%HIT_DELAY%"],
				["HIT_DISARMED", "%HIT_DISARMED%"],
				["HIT_DOWN", "%HIT_DOWN%"],
				["HIT_EAST", "%HIT_EAST%"],
				["HIT_ENABLED", "%HIT_ENABLED%"],
				["HIT_EXPLODE", "%HIT_EXPLODE%"],
				["HIT_EXTENDED", "%HIT_EXTENDED%"],
				["HIT_EYE", "%HIT_EYE%"],
				["HIT_FACING", "%HIT_FACING%"],
				["HIT_HALF", "%HIT_HALF%"],
				["HIT_HAS_BOTTLE_0", "%HIT_HAS_BOTTLE_0%"],
				["HIT_HAS_BOTTLE_1", "%HIT_HAS_BOTTLE_1%"],
				["HIT_HAS_BOTTLE_2", "%HIT_HAS_BOTTLE_2%"],
				["HIT_HAS_RECORD", "%HIT_HAS_RECORD%"],
				["HIT_HINGE", "%HIT_HINGE%"],
				["HIT_IN_WALL", "%HIT_IN_WALL%"],
				["HIT_LAYERS", "%HIT_LAYERS%"],
				["HIT_LEGACY_DATA", "%HIT_LEGACY_DATA%"],
				["HIT_LEVEL", "%HIT_LEVEL%"],
				["HIT_LOCKED", "%HIT_LOCKED%"],
				["HIT_MODE", "%HIT_MODE%"],
				["HIT_MOISTURE", "%HIT_MOISTURE%"],
				["HIT_NODROP", "%HIT_NODROP%"],
				["HIT_NORTH", "%HIT_NORTH%"],
				["HIT_OCCUPIED", "%HIT_OCCUPIED%"],
				["HIT_OPEN", "%HIT_OPEN%"],
				["HIT_PART", "%HIT_PART%"],
				["HIT_POWER", "%HIT_POWER%"],
				["HIT_POWERED", "%HIT_POWERED%"],
				["HIT_ROTATION", "%HIT_ROTATION%"],
				["HIT_SEAMLESS", "%HIT_SEAMLESS%"],
				["HIT_SHAPE", "%HIT_SHAPE%"],
				["HIT_SHORT", "%HIT_SHORT%"],
				["HIT_SNOWY", "%HIT_SNOWY%"],
				["HIT_SOUTH", "%HIT_SOUTH%"],
				["HIT_STAGE", "%HIT_STAGE%"],
				["HIT_TRIGGERED", "%HIT_TRIGGERED%"],
				["HIT_TYPE", "%HIT_TYPE%"],
				["HIT_UP", "%HIT_UP%"],
				["HIT_VARIANT", "%HIT_VARIANT%"],
				["HIT_WEST", "%HIT_WEST%"],
				["HIT_WET", "%HIT_WET%"],
				["HITDATA\tMetadata of the thing the Player is looking at", "%HITDATA%"],
				["HITID\tID of the thing the Player is looking at", "%HITID%"],
				["HITNAME\tDisplayname of the thing the Player is looking at", "%HITNAME%"],
				["HITPROGRESS\tBlock breaking progress of the block the Player is looking at", "%HITPROGRESS%"],
				["HITSIDE\tBlock side of the block the Player is looking at", "%HITSIDE%"],
				["HITUUID\tUUID of the looked at entity or player", "%HITUUID%"],
				["HITX\tX position of the block the Player is looking at", "%HITX%"],
				["HITY\tY position of the block the Player is looking at", "%HITY%"],
				["HITZ\tZ position of the block the Player is looking at", "%HITZ%"],
				["HOSTILEVOLUME\tVolume level for Hostile Creatures", "%HOSTILEVOLUME%"],
				["HUNGER\tHunger points (each icon equals 2 points)", "%HUNGER%"],
				["IIF\tInline IF statement", "IIF(${1:<condition>},${2:<truetext>},${3:[falsetext]});"],
				["IMPORT\tOverlay the specified configuration", "IMPORT(${1:<configname>});"],
				["INC\tIncrements the specified counter by 1 or by the specified amount", "INC(#${1:<var>},${2:[amount]});"],
				["INDEXOF\tGets the first index of a item", "INDEXOF(${1:<array>}[],#${2:<outvar>},${3:<searchfor>},${4:[casesensitiv]});"],
				["INVENTORYDOWN\tScrolls the specified number of slots down through the hotbar", "INVENTORYDOWN(${1:[amount]});"],
				["INVENTORYUP\tScrolls the specified number of slots up through the hotbar", "INVENTORYUP(${1:[amount]});"],
				["INVSLOT\tSelected inventory slot", "%INVSLOT%"],
				["ISRUNNING\tReturns whether the specified macro is currently running", "ISRUNNING(${1:<macro>});"],
				["ITEM\tID of the equipped item", "%ITEM%"],
				["ITEMCODE\tInternal code for the equipped item", "%ITEMCODE%"],
				["ITEMDAMAGE\tMaximum uses of the equipped item", "%ITEMDAMAGE%"],
				["ITEMID\tGets the legacy (numeric) ID for the specified item", "ITEMID(${1:<item>});"],
				["ITEMIDDMG\tID and durability seperated by a colon of the equipped item", "%ITEMIDDMG%"],
				["ITEMNAME\tDisplayname for the equipped item", "%ITEMNAME%"],
				["ITEMNAME\tGet the item descriptor for a legacy (numeric) item ID", "ITEMNAME(${1:<id>});"],
				["ITEMUSEPCT\tPrevious value as percent of total useage time", "%ITEMUSEPCT%"],
				["ITEMUSETICKS \tAll usable items increase this value once per tick", "%ITEMUSETICKS%"],
				["JOIN\tCombines values inside array with glue", "JOIN(${1:<glue>},${2:<array>}[],&${3:[output]});"],
				["JOINEDPLAYER\t(onPlayerJoined) Player name of the newly joined player", "%JOINEDPLAYER%"],
				["KEY\tActivates the specified key binding for 1 tick", "KEY(${1:<bind>});"],
				["KEY_0", "%KEY_0%"],
				["KEY_1", "%KEY_1%"],
				["KEY_2", "%KEY_2%"],
				["KEY_3", "%KEY_3%"],
				["KEY_4", "%KEY_4%"],
				["KEY_5", "%KEY_5%"],
				["KEY_6", "%KEY_6%"],
				["KEY_7", "%KEY_7%"],
				["KEY_8", "%KEY_8%"],
				["KEY_9", "%KEY_9%"],
				["KEY_A", "%KEY_A%"],
				["KEY_ADD", "%KEY_ADD%"],
				["KEY_APOSTROPHE", "%KEY_APOSTROPHE%"],
				["KEY_APPS", "%KEY_APPS%"],
				["KEY_AT", "%KEY_AT%"],
				["KEY_AX", "%KEY_AX%"],
				["KEY_B", "%KEY_B%"],
				["KEY_BACK", "%KEY_BACK%"],
				["KEY_BACKSLASH", "%KEY_BACKSLASH%"],
				["KEY_C", "%KEY_C%"],
				["KEY_CAPITAL", "%KEY_CAPITAL%"],
				["KEY_CIRCUMFLEX", "%KEY_CIRCUMFLEX%"],
				["KEY_CLEAR", "%KEY_CLEAR%"],
				["KEY_COLON", "%KEY_COLON%"],
				["KEY_COMMA", "%KEY_COMMA%"],
				["KEY_CONVERT", "%KEY_CONVERT%"],
				["KEY_D", "%KEY_D%"],
				["KEY_DECIMAL", "%KEY_DECIMAL%"],
				["KEY_DELETE", "%KEY_DELETE%"],
				["KEY_DIVIDE", "%KEY_DIVIDE%"],
				["KEY_DOWN", "%KEY_DOWN%"],
				["KEY_E", "%KEY_E%"],
				["KEY_END", "%KEY_END%"],
				["KEY_EQUALS", "%KEY_EQUALS%"],
				["KEY_ESCAPE", "%KEY_ESCAPE%"],
				["KEY_F", "%KEY_F%"],
				["KEY_F1", "%KEY_F1%"],
				["KEY_F10", "%KEY_F10%"],
				["KEY_F11", "%KEY_F11%"],
				["KEY_F12", "%KEY_F12%"],
				["KEY_F13", "%KEY_F13%"],
				["KEY_F14", "%KEY_F14%"],
				["KEY_F15", "%KEY_F15%"],
				["KEY_F16", "%KEY_F16%"],
				["KEY_F17", "%KEY_F17%"],
				["KEY_F18", "%KEY_F18%"],
				["KEY_F19", "%KEY_F19%"],
				["KEY_F2", "%KEY_F2%"],
				["KEY_F3", "%KEY_F3%"],
				["KEY_F4", "%KEY_F4%"],
				["KEY_F5", "%KEY_F5%"],
				["KEY_F6", "%KEY_F6%"],
				["KEY_F7", "%KEY_F7%"],
				["KEY_F8", "%KEY_F8%"],
				["KEY_F9", "%KEY_F9%"],
				["KEY_FUNCTION", "%KEY_FUNCTION%"],
				["KEY_G", "%KEY_G%"],
				["KEY_GRAVE", "%KEY_GRAVE%"],
				["KEY_H", "%KEY_H%"],
				["KEY_HOME", "%KEY_HOME%"],
				["KEY_I", "%KEY_I%"],
				["KEY_INSERT", "%KEY_INSERT%"],
				["KEY_J", "%KEY_J%"],
				["KEY_K", "%KEY_K%"],
				["KEY_KANA", "%KEY_KANA%"],
				["KEY_KANJI", "%KEY_KANJI%"],
				["KEY_L", "%KEY_L%"],
				["KEY_LBRACKET", "%KEY_LBRACKET%"],
				["KEY_LCONTROL", "%KEY_LCONTROL%"],
				["KEY_LEFT", "%KEY_LEFT%"],
				["KEY_LMENU", "%KEY_LMENU%"],
				["KEY_LMETA", "%KEY_LMETA%"],
				["KEY_LSHIFT", "%KEY_LSHIFT%"],
				["KEY_M", "%KEY_M%"],
				["KEY_MINUS", "%KEY_MINUS%"],
				["KEY_MOUSE3", "%KEY_MOUSE3%"],
				["KEY_MOUSE4", "%KEY_MOUSE4%"],
				["KEY_MULTIPLY", "%KEY_MULTIPLY%"],
				["KEY_N", "%KEY_N%"],
				["KEY_NEXT", "%KEY_NEXT%"],
				["KEY_NOCONVERT", "%KEY_NOCONVERT%"],
				["KEY_NONE", "%KEY_NONE%"],
				["KEY_NUMLOCK", "%KEY_NUMLOCK%"],
				["KEY_NUMPAD0", "%KEY_NUMPAD0%"],
				["KEY_NUMPAD1", "%KEY_NUMPAD1%"],
				["KEY_NUMPAD2", "%KEY_NUMPAD2%"],
				["KEY_NUMPAD3", "%KEY_NUMPAD3%"],
				["KEY_NUMPAD4", "%KEY_NUMPAD4%"],
				["KEY_NUMPAD5", "%KEY_NUMPAD5%"],
				["KEY_NUMPAD6", "%KEY_NUMPAD6%"],
				["KEY_NUMPAD7", "%KEY_NUMPAD7%"],
				["KEY_NUMPAD8", "%KEY_NUMPAD8%"],
				["KEY_NUMPAD9", "%KEY_NUMPAD9%"],
				["KEY_NUMPADCOMMA", "%KEY_NUMPADCOMMA%"],
				["KEY_NUMPADENTER", "%KEY_NUMPADENTER%"],
				["KEY_NUMPADEQUALS", "%KEY_NUMPADEQUALS%"],
				["KEY_O", "%KEY_O%"],
				["KEY_P", "%KEY_P%"],
				["KEY_PAUSE", "%KEY_PAUSE%"],
				["KEY_PERIOD", "%KEY_PERIOD%"],
				["KEY_POWER", "%KEY_POWER%"],
				["KEY_PRIOR", "%KEY_PRIOR%"],
				["KEY_Q", "%KEY_Q%"],
				["KEY_R", "%KEY_R%"],
				["KEY_RBRACKET", "%KEY_RBRACKET%"],
				["KEY_RCONTROL", "%KEY_RCONTROL%"],
				["KEY_RETURN", "%KEY_RETURN%"],
				["KEY_RIGHT", "%KEY_RIGHT%"],
				["KEY_RMENU", "%KEY_RMENU%"],
				["KEY_RMETA", "%KEY_RMETA%"],
				["KEY_RSHIFT", "%KEY_RSHIFT%"],
				["KEY_S", "%KEY_S%"],
				["KEY_SCROLL", "%KEY_SCROLL%"],
				["KEY_SECTION", "%KEY_SECTION%"],
				["KEY_SEMICOLON", "%KEY_SEMICOLON%"],
				["KEY_SLASH", "%KEY_SLASH%"],
				["KEY_SLEEP", "%KEY_SLEEP%"],
				["KEY_SPACE", "%KEY_SPACE%"],
				["KEY_STOP", "%KEY_STOP%"],
				["KEY_SUBTRACT", "%KEY_SUBTRACT%"],
				["KEY_SYSRQ", "%KEY_SYSRQ%"],
				["KEY_T", "%KEY_T%"],
				["KEY_TAB", "%KEY_TAB%"],
				["KEY_U", "%KEY_U%"],
				["KEY_UNDERLINE", "%KEY_UNDERLINE%"],
				["KEY_UNLABELED", "%KEY_UNLABELED%"],
				["KEY_UP", "%KEY_UP%"],
				["KEY_V", "%KEY_V%"],
				["KEY_W", "%KEY_W%"],
				["KEY_X", "%KEY_X%"],
				["KEY_Y", "%KEY_Y%"],
				["KEY_YEN", "%KEY_YEN%"],
				["KEY_Z", "%KEY_Z%"],
				["KEYDOWN\tSets the specified key binding state to pressed, only works with pressable bindings", "KEYDOWN(${1:<bind>});"],
				["KEYID\tKey ID of the key that started this script", "%KEYID%"],
				["KEYNAME\tKeyname of the key that started this script", "%KEYNAME%"],
				["KEYUP\tSets the specified key binding state to unpressed, only works with pressable bindings", "KEYUP(${1:<bind>});"],
				["LCASE\tConverts the input string to lower case and stores it in output", "LCASE(${1:<input>},&${2:[output]});"],
				["LEGGINGSDAMAGE\tMaximum uses of the Players leggings", "%LEGGINGSDAMAGE%"],
				["LEGGINGSDURABILITY\tDurability of the Players leggings", "%LEGGINGSDURABILITY%"],
				["LEGGINGSID\tID of the Players leggings", "%LEGGINGSID%"],
				["LEGGINGSNAME\tDisplayname of the Players leggings", "%LEGGINGSNAME%"],
				["LEVEL\tXP level", "%LEVEL%"],
				["LIGHT\tLight level at current location", "%LIGHT%"],
				["LMOUSE", "%LMOUSE%"],
				["LOCALDIFFICULTY\tLocal difficulty of the world", "%LOCALDIFFICULTY%"],
				["LOG\tShows the specified text only on the client-side in the chat window", "LOG(${1:<text>});"],
				["LOGRAW\tSimilar to minecraft tellraw command", "LOGRAW(${1:<json>});"],
				["LOGTO\tOutputs the specified text into the specified target", "LOGTO(${1:<target>},${2:<text>});"],
				["LOOK\tFaces the player in the specified direction", "LOOK(${1:<yaw>},${2:[pitch]},${3:[time]});"],
				["LOOKS\tSmoothly turnes the player to the specified direction", "LOOKS(${1:<yaw>},${2:[pitch]},${3:[time]});"],
				["MACROID\t(running iterator) Internal id of the macro", "%MACROID%"],
				["MACRONAME\t(running iterator) Display name of the macro", "%MACRONAME%"],
				["MACROTIME\t(running iterator) The time the macro is already running in seconds", "%MACROTIME%"],
				["MAINHANDCOOLDOWN\tmainhand cooldown", "%MAINHANDCOOLDOWN%"],
				["MAINHANDDURABILITY\tDurability of the mainhand item", "%MAINHANDDURABILITY%"],
				["MAINHANDITEM\tID of the mainhand item", "%MAINHANDITEM%"],
				["MAINHANDITEMCODE\tInternal code for the mainhand item", "%MAINHANDITEMCODE%"],
				["MAINHANDITEMDAMAGE\tMaximum uses of the mainhand item", "%MAINHANDITEMDAMAGE%"],
				["MAINHANDITEMIDDMG\tID and durability seperated by a colon of the mainhand item", "%MAINHANDITEMIDDMG%"],
				["MAINHANDITEMNAME\tDisplayname for the mainhand item", "%MAINHANDITEMNAME%"],
				["MAINHANDSTACKSIZE\tStacksize of the mainhand item", "%MAINHANDSTACKSIZE%"],
				["MATCH\tRuns a regular expression match on the subject", "MATCH(${1:<subject>},${2:<pattern>},&${3:[target]},${4:[group]},${5:[default]});"],
				["MAXPLAYERS\tAmount of players the server can hold", "%MAXPLAYERS%"],
				["MIDDLEMOUSE", "%MIDDLEMOUSE%"],
				["MODE\tGamemode of the player as a number", "%MODE%"],
				["MODIFY\tSet new content for this chat message", "MODIFY(${1:<newmessage>});"],
				["MUSIC\tVolume level for Music", "%MUSIC%"],
				["MUSIC\tSets the music volume, specifying time causes the value to change smoothly", "MUSIC(${1:<value>},${2:[time]});"],
				["NEUTRALVOLUME\tVolume level for Friendly Creatures", "%NEUTRALVOLUME%"],
				["NEXT\tCompletes a for or foreach loop", "NEXT;"],
				["OFFHANDCOOLDOWN\tOffhand cooldown", "%OFFHANDCOOLDOWN%"],
				["OFFHANDDURABILITY\tDurability of the offhand item", "%OFFHANDDURABILITY%"],
				["OFFHANDITEM\tID of the offhand item", "%OFFHANDITEM%"],
				["OFFHANDITEMCODE\tInternal code for the offhand item", "%OFFHANDITEMCODE%"],
				["OFFHANDITEMDAMAGE\tMaximum uses of the offhand item", "%OFFHANDITEMDAMAGE%"],
				["OFFHANDITEMIDDMG\tID and durability seperated by a colon of the offhand item", "%OFFHANDITEMIDDMG%"],
				["OFFHANDITEMNAME\tDisplayname for the offhand item", "%OFFHANDITEMNAME%"],
				["OFFHANDSTACKSIZE\tStacksize of the offhand item", "%OFFHANDSTACKSIZE%"],
				["OLDINVSLOT\t(onInventorySlotChange) Selected inventory slot before it was changed", "%OLDINVSLOT%"],
				["ONLINEPLAYERS\tAmount of players currently on the server", "%ONLINEPLAYERS%"],
				["OXYGEN\tAir Level (from 0 to 300)", "%OXYGEN%"],
				["PASS\tIndicate that this chat message should PASS the filter and terminate", "PASS;"],
				["PICK\tSelects the specified item id if it is on the hotbar", "PICK(${1:<item>}:${2:[damage]},${3:<item>}:${4:[damage]}${5:,...});"],
				["PICKUPAMOUNT\t(onPickupItem) Amount of items picked up", "%PICKUPAMOUNT%"],
				["PICKUPDATA\t(onPickupItem) Metadata of the picked up item", "%PICKUPDATA%"],
				["PICKUPID\t(onPickupItem) Item id of the picked up item", "%PICKUPID%"],
				["PICKUPITEM\t(onPickupItem) Display name of the picked up item", "%PICKUPITEM%"],
				["PITCH\tPitch of the player", "%PITCH%"],
				["PLACESIGN\tPlaces a sign in the world with the specified text", "PLACESIGN(${1:[line1]},${2:[line2]},${3:[line3]},${4:[line4]},${5:[showgui]});"],
				["PLAYER\tPlayer's name", "%PLAYER%"],
				["PLAYERNAME\t(players iterator) The current player", "%PLAYERNAME%"],
				["PLAYERS\tIterates over all online players", "players"],
				["PLAYERVOLUME\tVolume level for Players", "%PLAYERVOLUME%"],
				["PLAYSOUND\tPlays the specified sound", "PLAYSOUND(${1:<sound>},${2:[volume]});"],
				["POP\tRemoves the last entry from the end of array and stores it in outvar", "POP(${1:<array>}[],${2:<outvar>});"],
				["POPUPMESSAGE\tDisplay a message in the area above the hotbar", "POPUPMESSAGE(${1:<message>},${2:[animate]});"],
				["PRESS\tInjects the specified key event directly into the keyboard buffer for 1 tick", "PRESS(${1:<lwjgl_name>},${2:[deep]});"],
				["PROMPT\tDisplays a prompt by parsing the params in paramstring", "PROMPT(&${1:<target>},${2:<paramstring>},${3:[prompt]},${4:[override]},${5:[default]});"],
				["PROPERTIES\tIterates over all properties of the block you are looking at", "properties"],
				["PROPNAME\t(properties iterator) The name of the current property", "%PROPNAME%"],
				["PROPVALUE\t(properties iterator) The value of the current property", "%PROPVALUE%"],
				["PUSH\tAppends value to the end of array[]", "PUSH(${1:<array>}[],${2:<value>});"],
				["PUT\tInserts value at the first empty point in array[]", "PUT(${1:<array>}[],${2:<value>});"],
				["RAIN\tRain level", "%RAIN%"],
				["RANDOM\tAssigns a random number between min and max to target", "RANDOM(#${1:<target>},${2:[max]},${3:[min])};"],
				["REASON\t(onAutoCraftingComplete) The reason why the crafting was completed or aborted", "%REASON%"],
				["RECORDVOLUME\tVolume level for Jukebox/Noteblocks", "%RECORDVOLUME%"],
				["REGEXREPLACE\tReplace all matches of pattern with replace in &subject", "REGEXREPLACE(&${1:<subject>},${2:<pattern>},${3:[replace]});"],
				["RELOADRESOURCES\tReloads resource packs, same as pressing F3 + T", "RELOADRESOURCES;"],
				["REPL\tAccess the REPL interface", "REPL;"],
				["REPLACE\tReplace all occurrences of search with replace in &subject", "REPLACE(&${1:<subject>},${2:<search>},${3:[replace]});"],
				["RESOURCEPACK", "RESOURCEPACK([pattern]);"],
				["RESOURCEPACKS\tSets the resource pack stack to the order matching the specified patterns", "RESOURCEPACKS(${1:[pattern]},${2:[pattern...]});"],
				["RESOURCEPACKS[]\tArray of selected resource packs", "%RESOURCEPACKS[]%"],
				["RESPAWN\tRespawns the player if you are dead", "RESPAWN();"],
				["RMOUSE", "%RMOUSE%"],
				["RUNNING\tIterates over all currently running macros", "running"],
				["SATURATION\tSaturation level (normally hidden from the Player)", "%SATURATION%"],
				["SCREEN\tName of the current custom GUI", "%SCREEN%"],
				["SCREENNAME\tDisplay name of the current custom GUI", "%SCREENNAME%"],
				["SEED\tSeed of the world (only available in SP)", "%SEED%"],
				["SELECTCHANNEL", "SELECTCHANNEL(${1:<channel>});"],
				["SENDMESSAGE", "SENDMESSAGE(${1:[params]});"],
				["SENSITIVITY\tSensitivity", "%SENSITIVITY%"],
				["SENSITIVITY\tSets the mouse sensitivity, specifying time causes the value to change smoothly", "SENSITIVITY(${1:<value>},${2:[time]});"],
				["SERVER\tIP of the server", "%SERVER%"],
				["SERVERMOTD\tMotto of the day of the server", "%SERVERMOTD%"],
				["SERVERNAME\tName of the server", "%SERVERNAME%"],
				["SET\tSets the value of target to value", "SET(${1:<target>},${2:[value]});"],
				["SETLABEL\tSets the text (and optionally binding) of the specified label", "SETLABEL(${1:<labelname>},${2:<text>},${3:[binding]});"],
				["SETPROPERTY\tSets the value of the specified property on the specified GUI control", "SETPROPERTY(${1:<control>},${2:<property>},${3:<value>});"],
				["SETRES\tSets the size of the minecraft game window", "SETRES(${1:<width>},${2:<height>});"],
				["SETSLOTITEM\tCreative mode only, set the contents of a hot bar slot", "SETSLOTITEM(${1:<item>}:${2:[damage]},${3:[slot]},${4:[amount]});"],
				["SHADERGROUP\tSelected shader", "%SHADERGROUP%"],
				["SHADERGROUP\tSets the active shader group to the shader matching path", "SHADERGROUP(${1:[path]});"],
				["SHADERGROUPS[]\tArray of available shaders", "%SHADERGROUPS[]%"],
				["SHIFT", "%SHIFT%"],
				["SHOWGUI\tShow a custom gui screen, creates it if it doesn't exist", "SHOWGUI(${1:<screen>},${2:[esc_screen]},${3:[macro_keys]});"],
				["SIGNTEXT[]\tArray of lines on a sign the Player is looking at", "%SIGNTEXT[]%"],
				["SLOT\tSelects the specified slot on the hot bar", "SLOT(${1:<slot>});"],
				["SLOTCLICK\tSimulates clicking on the specified slot in the current GUI", "SLOTCLICK(${1:<slot>},${2:[button]},${3:[shift]});"],
				["SOUND\tMaster Volume level", "%SOUND%"],
				["SPLIT\tSplits the supplied source string on every delimiter into output[]", "SPLIT(${1:<delimiter>},${2:<source>},${3:[output]}[]);"],
				["SPRINT\tSets the player state to sprinting if sufficient stamina (food)", "SPRINT();"],
				["SQRT\tCalculate the rounded square root of value and store it in #outvar", "SQRT(${1:<value>},#${2:[outvar]});"],
				["STACKSIZE\tStack size of the equipped item", "%STACKSIZE%"],
				["STOP\tStops the current macro, or macros matching the specified ID", "STOP(${1:[id]});"],
				["STORE\tStores a value into one of the predefined parameter lists", "STORE(${1:<type>},${2:[name]});"],
				["STOREOVER\tStores a value into one of the predefined parameter lists and overwrites an entry if it already exists", "STOREOVER(${1:<type>},${2:[name]});"],
				["STRIP\tStrips all formatting codes from the specified text and assigns the result to &target", "STRIP(&${1:<target>},${2:<text>});"],
				["TEXTUREPACK", "texturepack${1:([pattern]});"],
				["TEXTUREPACK", "%TEXTUREPACK%"],
				["TICKS\tcurrent world time value (which will be a static number if doDayNightCycle game rule is false)", "%TICKS%"],
				["TILEID\tGets the legacy (numeric) ID for the specified tile", "TILEID(${1:<item>});"],
				["TILENAME\tGet the descriptor for a legacy (numeric) tile ID", "TILENAME(${1:<id>});"],
				["TIME\tStores the current time and date into &target, optionally using format specified", "TIME(&${1:<target>},${2:[format]});"],
				["TIME\tCurrent time in the format hour:minute:second", "%TIME%"],
				["TIMESTAMP\tUNIX Timestamp", "%TIMESTAMP%"],
				["TITLE\tDisplays the specified custom title, call with no arguments to hide current titles", "TITLE(${1:[title]},${2:[subtitle]},${3:[inticks]},${4:[showticks]},${5:[outticks]});"],
				["TOAST\tDisplays an user-defined toast", "TOAST(${1:[type]},${2:[icon]},${3:[text1]},${4:[text2]},${5:[ticks]});"],
				["TOGGLE\tToggles the specified boolean flag value", "TOGGLE(${1:[flag]});"],
				["TOGGLEKEY\tToggles the pressed state of the specified key binding, only works with pressable bindings", "TOGGLEKEY(${1:<bind>});"],
				["TOTALTICKS\tcurrent total world time (which increases all the time regardless of the gamerule doDayNightCycle)", "%TOTALTICKS%"],
				["TOTALXP\tTotal amount of experience points", "%TOTALXP%"],
				["TRACE\tPerforms a ray trace operation which sets the raytrace variables in the local scope", "TRACE(${1:<distance>},${2:[entities]});"],
				["TRACE_AGE", "%TRACE_AGE%"],
				["TRACE_ATTACHED", "%TRACE_ATTACHED%"],
				["TRACE_AXIS", "%TRACE_AXIS%"],
				["TRACE_BITES", "%TRACE_BITES%"],
				["TRACE_CHECK_DECAY", "%TRACE_CHECK_DECAY%"],
				["TRACE_COLOR", "%TRACE_COLOR%"],
				["TRACE_CONDITIONAL", "%TRACE_CONDITIONAL%"],
				["TRACE_CONTENTS", "%TRACE_CONTENTS%"],
				["TRACE_DAMAGE", "%TRACE_DAMAGE%"],
				["TRACE_DECAYABLE", "%TRACE_DECAYABLE%"],
				["TRACE_DELAY", "%TRACE_DELAY%"],
				["TRACE_DISARMED", "%TRACE_DISARMED%"],
				["TRACE_DOWN", "%TRACE_DOWN%"],
				["TRACE_EAST", "%TRACE_EAST%"],
				["TRACE_ENABLED", "%TRACE_ENABLED%"],
				["TRACE_EXPLODE", "%TRACE_EXPLODE%"],
				["TRACE_EXTENDED", "%TRACE_EXTENDED%"],
				["TRACE_EYE", "%TRACE_EYE%"],
				["TRACE_FACING", "%TRACE_FACING%"],
				["TRACE_HALF", "%TRACE_HALF%"],
				["TRACE_HAS_BOTTLE_0", "%TRACE_HAS_BOTTLE_0%"],
				["TRACE_HAS_BOTTLE_1", "%TRACE_HAS_BOTTLE_1%"],
				["TRACE_HAS_BOTTLE_2", "%TRACE_HAS_BOTTLE_2%"],
				["TRACE_HAS_RECORD", "%TRACE_HAS_RECORD%"],
				["TRACE_HINGE", "%TRACE_HINGE%"],
				["TRACE_IN_WALL", "%TRACE_IN_WALL%"],
				["TRACE_LAYERS", "%TRACE_LAYERS%"],
				["TRACE_LEGACY_DATA", "%TRACE_LEGACY_DATA%"],
				["TRACE_LEVEL", "%TRACE_LEVEL%"],
				["TRACE_LOCKED", "%TRACE_LOCKED%"],
				["TRACE_MODE", "%TRACE_MODE%"],
				["TRACE_MOISTURE", "%TRACE_MOISTURE%"],
				["TRACE_NODROP", "%TRACE_NODROP%"],
				["TRACE_NORTH", "%TRACE_NORTH%"],
				["TRACE_OCCUPIED", "%TRACE_OCCUPIED%"],
				["TRACE_OPEN", "%TRACE_OPEN%"],
				["TRACE_PART", "%TRACE_PART%"],
				["TRACE_POWER", "%TRACE_POWER%"],
				["TRACE_POWERED", "%TRACE_POWERED%"],
				["TRACE_ROTATION", "%TRACE_ROTATION%"],
				["TRACE_SEAMLESS", "%TRACE_SEAMLESS%"],
				["TRACE_SHAPE", "%TRACE_SHAPE%"],
				["TRACE_SHORT", "%TRACE_SHORT%"],
				["TRACE_SNOWY", "%TRACE_SNOWY%"],
				["TRACE_SOUTH", "%TRACE_SOUTH%"],
				["TRACE_STAGE", "%TRACE_STAGE%"],
				["TRACE_TRIGGERED", "%TRACE_TRIGGERED%"],
				["TRACE_TYPE", "%TRACE_TYPE%"],
				["TRACE_UP", "%TRACE_UP%"],
				["TRACE_VARIANT", "%TRACE_VARIANT%"],
				["TRACE_WEST", "%TRACE_WEST%"],
				["TRACE_WET", "%TRACE_WET%"],
				["TRACEDATA\tMetadata of the block", "%TRACEDATA%"],
				["TRACEID\tThe id", "%TRACEID%"],
				["TRACENAME\tThe name", "%TRACENAME%"],
				["TRACESIDE\tSide of the block", "%TRACESIDE%"],
				["TRACETYPE\tThe type of the result", "%TRACETYPE%"],
				["TRACEUUID\tReturns the UUID of other players", "%TRACEUUID%"],
				["TRACEX\tX position", "%TRACEX%"],
				["TRACEY\tY position", "%TRACEY%"],
				["TRACEZ\tZ position", "%TRACEZ%"],
				["TYPE\tInjects the specified key sequence directly into the keyboard buffer at a rate of 1 key per tick", "TYPE(${1:<text>});"],
				["UCASE\tConverts the input string to upper case and stores it in output", "UCASE(${1:<input>},&${2:[output]});"],
				["UNIMPORT\tRemove the specified configuration overlay if active", "UNIMPORT();"],
				["UNIQUEID\tReturns a new UUID everytime it is accessed", "%UNIQUEID%"],
				["UNSET\tUn-sets the specified flag variable", "UNSET(${1:<flag>});"],
				["UNSPRINT\tSets the player state to not sprinting", "UNSPRINT();"],
				["UUID\tUUID of the Player", "%UUID%"],
				["VARNAME\t(env iterator) Contains the variable name", "%VARNAME%"],
				["VEHICLE\tVehicle type", "%VEHICLE%"],
				["VEHICLEHEALTH\tVehicle health", "%VEHICLEHEALTH%"],
				["VOLUME\tSets the sound volume for the specified category", "VOLUME(${1:<value>},${2:[category]});"],
				["WAIT\tPauses the script for the time specified", "WAIT(${1:<time>});"],
				["WALKTO\tWas never offically in the mod", "WALKTO(${1:<x>},${2:<y>},${3:<z>},${4:[speed]},${5:[radius]});"],
				["WEATHERVOLUME\tVolume level for Weather", "%WEATHERVOLUME%"],
				["XP\tCurrent amount of experience points", "%XP%"],
				["XPOS\tPosition in X direction", "%XPOS%"],
				["XPOSF\tThe position in X direction with three decimal places after the comma as a string", "%XPOSF%"],
				["YAW\tYaw of the player", "%YAW%"],
				["YPOS\tPosition in Y direction", "%YPOS%"],
				["YPOSF\tThe position in Y direction with three decimal places after the comma as a string", "%YPOSF%"],
				["ZPOS\tPosition in Z direction", "%ZPOS%"],
				["ZPOSF\tThe position in Z direction with three decimal places after the comma as a string", "%ZPOSF%"]
			],sublime.INHIBIT_EXPLICIT_COMPLETIONS)