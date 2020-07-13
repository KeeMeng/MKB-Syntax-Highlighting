import sublime
import sublime_plugin
import json
import os 
dir_path = os.path.dirname(os.path.realpath(__file__)) + "/MKBdocs.json"
# https://beta.mkb.gorlem.ml/api/docs

class mkbcompletions(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if not view.match_selector(locations[0], "mkb"):
            return None

        with open(dir_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        caps = prefix.islower()
        for i in data:
            if i['name'].lower() == prefix.lower() and ( i['resource'].startswith("/api/docs/actions/") or i['resource'].startswith("/api/docs/commands/") ):
                if caps:
                    return [["%s\t%s"%(prefix.lower(),i['extendedName'].lower()), "%s;"%(i['extendedName'].lower())]]
                else:
                    return [["%s\t%s"%(prefix,i['extendedName']), "%s;"%(i['extendedName'])]] 
                break
