# MKB-Syntax-Highlighting
## Macro/Keybind Mod Syntax Highlighting for Sublime Text 3 with Auto Complete

**Supports common modules too**

*You could modify it to work on your own text editor, probably by using the regular expression matches and captures. You could also reference the minecraft hex color codes, which are pretty nice.*

---

## Introduction:

There are 5 files which you need to download, and place in your Packages/User folder: 
- **MKB.json**: is for the custom colors and rules.
- **MKB.py**: Is a Python plugin file, which will get data from **MKBdocs.json** 
- **MKB.sublime-completions**:  Is a JSON file, containing specific "triggers", which will activate the auto complete, adding in the "contents". 
- **MKB.sublime-syntax**: Is a YAML file, with many regexes and assigning scopes to them.
- **MKBdocs.json**: Is a JSON API, containing the MKB wiki made by gorlem, found here https://beta.mkb.gorlem.ml/api/docs. This page might be updated from time to time. 

**Useful links:**
- https://packagecontrol.io/installation
- https://github.com/SublimeText/PackageDev/blob/master/README.md
- https://www.sublimetext.com/docs/3/syntax.html
- http://www.sublimetext.com/docs/3/color_schemes.html
- https://docs.sublimetext.io/guide/extensibility/completions.html#completed-completions
- https://docs.sublimetext.io/guide/extensibility/plugins/

---

## Set Up: 

You need to get the PackageDev for this, by doing `Preferences > Package Control` and then type `Package Control: Install Package`. Afterwards, search `PackageDev` in the menu and install it. You might need to restart Sublime Text 3. 

First, you need to add the custom colors in **MKB.json**, and to do that you go to. `Tools > Packages > Package Development > Edit Current Color Scheme...` Paste the entire json contents into the **Right Side** of the color scheme, the top of the file should say THEME.sublime-color-scheme — USER. 

Next, you can drag the other 4 files (**MKB.py**, **MKB.sublime-completions**, **MKB.sublime-syntax**, **MKBdocs.json**) into the place where you Sublime Text 3 folder is (For Mac, it is located in `/Users/NAME/Library/Application Support/Sublime Text 3/Packages/User`).

*Note that the menus might be different depending on your os, so you can always use the text editor's help.*

---

## Usage:

When opening a txt or rtf file (can be configured), and the first line is `$${`, it will automatically change to `MKB` syntax. But if it doesnt work, then you can go to the bottom right corner, and change `Plain Text` to `MKB` syntax. After that, the colors should appear automatically, along with the auto complete functions. To auto complete a statement, press tab and cycle through the options, or CMD/CTRL + Space to see a list of the possible auto completions. 

---

## How does it work?

The new sublime syntax will recognize the actions, variables, parameters, iterators and many more keywords of the Macro/Keybind Mod (Also the modules from https://spthiel.github.io/Modules), using regex statements it assigns a scope to it. The scope is then assigned a color in the color scheme file, and then you get custom syntax highlighting! The default scope is mkb, and the python plugin file will make sure that it is only working in this scope. The completions file will help you auto complete statements, also showing basic help for the statement when you press tab. 

---

## Others

If there are any bugs, please tell me, or report it in GitHub. My discord is TKM#6228. If there are any suggestions, please tell me too! 
