# MKB-Syntax-Highlighting
## Macro/Keybind Mod Syntax Highlighting for Sublime Text 3 with Auto Complete and hints

**Syntax highlighting & auto complete supports modules from https://spthiel.github.io/Modules/**
**Also contains an auto indenter made by Federal**

https://packagecontrol.io/packages/MKB

---

## Introduction:

This package was made to help coding for Macro Keybind Mod easier. To help you, I made auto complete to suggest possible actions and variable to you, and if you hover over the keywords, you can see a description and example of the command, which was taken from https://beta.mkb.gorlem.ml/api/docs. (Thanks Gorlem!) It also has an indenter made by Federal, with a fancy indent function too! After making your code, you can also use a linter to find possible bugs, such as missing brackets. To personalize this package, go to the Context Menu or `Edit` > `MKB` menu at the top of Sublime Text 3, and modify `Package Settings`. 

Brief description of the files in the package include: 
```
File                          | Description
MKB.py                        | Is a Python plugin file, which controls all the popups, autocompletes, indenting, and linter.
MKBdocs.css                   | CSS for dark mode on wiki
MKBdocs.json                  | Gorlem's wiki API used for popup hints.
Main.sublime-menu             | JSON file for the menu at the top.
MKB.sublime-syntax            | Is a YAML file, with many regexes and assigning scopes to the text to make them colorful.
Context.sublime-menu          | JSON file for the menu when you right click the screen.
MKB.sublime-settings          | JSON file for the settings to customize the package.
Default.sublime-keymap        | Auto %% when typing one %. 
MKB.sublime-completions       | Is a JSON file, containing specific "triggers", which will activate the auto complete.
MKB.sublime-color-scheme      | Is a json file for the custom colors of the syntax highlighter.
Miscellaneous.tmPreferences   | Helps with toggling comments.
template.sublime-color-scheme | Template to make your own color scheme (You can send it to me too)
```

---

## Installing using Package Control

**1)** If you haven't, install [Package Control](http://www.sublimelinter.com/en/stable/installation.html). 

**2)** Open Package Control: Install Package in the command palette, and search for MKB. Install it, and you might need to restart sublime. 

**3)** Change the language from `Plain Text` to `MKB` as your language. You can do this by selecting it at the bottom right corner menu. Sometimes you need to show your status bar (`View/Show Status Bar`). Alternative, you can right click the screen, click `MKB` > `MKB Language`

**4)** You can also click `MKB` > `Package Settings`, and personalize the package eg color scheme, indentation and many other

**5)** Enjoy! If there's anything wrong ask in #•help

---

## Manual installation
<details>
	<p>
		1) Install Sublime Text
	</p>
	<p>
		2) Install Package Dev
	</p>
	<p>
		3) Download/clone the repository from https://github.com/KeeMeng/MKB-Syntax-Highlighting
	</p>
	<p>
		4) Add the custom colors from **MKB.sublime-color-scheme**, into `Tools > Packages > Package Development > Edit Current Color Scheme...` Paste the entire json contents into the **Right Side** of the color scheme, the top of the file should say "THEME.sublime-color-scheme — USER". Read [this website](https://github.com/Iceshades/ST3-MKB-color-scheme) for more details.
	</p>
	<p>
		5) Put all the files from the repository into a MKB folder
		Path for Mac: ```/Users/NAME/Library/Application Support/Sublime Text 3/Packages/MKB```
		Path for windows: ```C:\Users\%USERNAME%\AppData\Roaming\Sublime Text 3\Packages\[MKB Folder here]```
	</p>
	<p>
		6) Change the language from `Plain Text` to `MKB` as your language. You can do this by selecting it at the bottom right corner menu. Sometimes you need to show your status bar (`View/Show Status Bar`)
	</p>
	<p>
		7) Go to the top menu, and click `MKB/Package Settings`, and personalize the package!
	</p>
	<p>
		8) Select MKB as you language by clicking the bottom right box (If it doesn't show go `view > show status bar`)
	</p>
	<p>
		9) Enjoy! If there's anything wrong ask in #•help
	</p>
</details>

---

## Usage:

- When opening a .txt file (can be configured), and the first line is `$${`, it will automatically change to `MKB` syntax. But if it doesnt work, then you can go to the bottom right corner, and change `Plain Text` to `MKB` syntax. After that, the colors should appear automatically, along with the auto complete functions. 
- To auto complete a statement, the auto complete menu should automatically appear. Press arrow key up or down to scroll through, press enter to auto complete. Then, press tab and jump to the next parameters. 
- Or press CMD/CTRL + Space to see a list of the possible auto completions. 
- You can also press CTRL + SHIFT + Space to open the inbuilt wiki.
- To indent your code, you can mess with the settings (Indent when you save, or prompt before it indents). Or, if you want to manually indent, right click the screen and press `MKB indent`.
- By default, when you hover over a keyword, you will see a popup with information. To manually show the hint, you can press `MKB Hint` when you right click. Scroll down for examples, or click "Open Wiki" to open the wiki page on your browser (Can be specified).
- Right click anywhere for some actions, or go to to `Edit > MKB` in the top main menu.
- You can also change the color scheme in `MKB > Package Settings`, as well as other cool settings
- If you want to make your own color scheme, follow the steps in `MKB > Color Scheme`

---

## How does it work?

- The new sublime syntax will recognize the actions, variables, parameters, iterators and many more keywords of the Macro/Keybind Mod (Also the modules from https://spthiel.github.io/Modules + a few others), using regex statements it assigns a scope to the different parts of your script. The scope is then assigned a color in the color scheme file, and then you get custom syntax highlighting! The default scope is source.mkb. 
- The completions file will help you auto complete statements, also showing basic help for the statement when you press tab. This uses the snippet function of sublime text. 
- The popup uses sublime's API and gorlem's API to find the information for the popup. 
- The indenter reads each line, and will automatically put tabs in front of the lines. Fancy indent adds a delay between indenting the lines, to make it look like a wave. 
- The linter reads each line and checks if theres an even number of `%% () "" []`
- The variable inserter finds all variables from the script

---

## Settings: 

<details>
	<p>
		- Which color scheme to use
	</p>
	<p>
		- Whether or not for the auto complete to be in uppercase
	</p>
	<p>
		- What character to use as the whitespace for the buffer
	</p>
	<p>
		- Whether or not indentation should expand compressed lines
	</p>
	<p>
		- Whether or not to end lines with semicolon ;
	</p>
	<p>
		- Whether or not to indent script between `$${` and `}$$`
	</p>
	<p>
		- Whether or not to automatically indent after saving the file
	</p>
	<p>
		- Whether or not to prompt a message before indenting, only if enable_indent is on
	</p>
	<p>
		- Whether or not to use fancy indenting. Put "null" for normal indenting, or put a number representing the delay in ms
	</p>
	<p>
		- Whether or not to show a message telling you indenting finished
	</p>
	<p>
		- Whether or not to show hints automatically
	</p>
	<p>
		- Number of lines to show in the pop up, put a big number to show everything
	</p>
	<p>
		- Whether or not to indent code after linting code
	</p>
	<p>
		- Whether or not to show a message after linting code
	</p>
	<p>
		- Whether or not to auto lint code after editing
	</p>
	<p>
		- Whether or not to show a message after minifying code
	</p>
	<p>
		- Which browser to use to open the wiki
	</p>
</details>

---

## Extra: 

**MKBdocs.css**: Is a css file to make https://beta.mkb.gorlem.ml/docs/actions have a dark mode. You can use a chrome extension called stylus to change the css. 

- [Chrome Extension](https://chrome.google.com/webstore/detail/stylus/clngdbkpkpeebahjckkjfobafhncgmne?hl=en-GB)
- [Safari Modify Elements](https://developer.apple.com/library/archive/documentation/NetworkingInternetWeb/Conceptual/Web_Inspector_Tutorial/EditingCode/EditingCode.html)
- [Mozilla/Firefox Style Editor](https://developer.mozilla.org/en-US/docs/Tools/Style_Editor)

---

## Others

If there are any bugs, please tell me, or report it in GitHub. My discord is TKM#6228. If there are any suggestions, please tell me too! 
Join https://discord.gg/m9yfJtb for support/suggestions/bugs.

Example of the syntax highlighter and the auto complete:
![Example](MKB-syntax-highlighting.png?raw=true)

Credits to:

- Federal for the Indenter
- Gorlem for the wiki
- Sublime Text Community for help (https://discord.gg/TZ5WN8t)

---

## Useful links
- https://packagecontrol.io/installation
- https://github.com/SublimeText/PackageDev/blob/master/README.md
- https://www.sublimetext.com/docs/3/syntax.html
- http://www.sublimetext.com/docs/3/color_schemes.html
- https://docs.sublimetext.io/guide/extensibility/completions.html#completed-completions
- https://docs.sublimetext.io/guide/extensibility/plugins/
- https://www.sublimetext.com/docs/3/api_reference.html
- https://www.youtube.com/channel/UCJAB_XF3kAMqwF85y0hxcXQ
- https://beta.mkb.gorlem.ml/api/docs
