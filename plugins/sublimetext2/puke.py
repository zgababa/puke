import sublime, sublime_plugin
import os, sys
import thread
import subprocess
import functools
import re
import string

class ProcessListener(object):
    def on_data(self, proc, data):
        pass

    def on_finished(self, proc):
        pass


PukeTasksList = []

class PukeExec:

    def cmd(self, command, path, callback):
        self.datas = []
        self.callback = callback
        self.proc = AsyncProcess(command, {}, self, path = path)
    
    def on_data(self, proc, data):
        data = data.replace('\r\n', '\n').replace('\r', '\n')
        data = re.sub('\[(\d+)m', '', data)
        self.datas.append(data)

    def on_finished(self, proc):
        sublime.set_timeout(functools.partial(self.finish, proc), 0)

    def finish(self, proc):
        self.callback(self.datas)
        if proc != self.proc:
            return

def checkPukeProject():
    pukefiles = ["pukefile", "pukeFile", "pukefile", "pukefile.py", "pukeFile.py", "pukefile.py"]
    script = None
    try:
        cwd = sublime.active_window().folders().pop()
    except Exception, msg:
        sublime.status_message("puke : not a project")
        return False

    for name in pukefiles:

        if os.path.isfile(os.path.join(cwd, name)):
            script = name

    if script is None:
        sublime.status_message("not a puke project")
        return False
    
    

    return True

# Encapsulates subprocess.Popen, forwarding stdout to a supplied
# ProcessListener (on a separate thread)
class AsyncProcess(object):
    def __init__(self, arg_list, env, listener,
            # "path" is an option in build systems
            path="",
            # "shell" is an options in build systems
            shell=False):
        
        self.listener = listener
        self.killed = False

        # Hide the console window on Windows
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # Set temporary PATH to locate executable in arg_list
        #if path:
        old_path = os.environ["PATH"]
            # The user decides in the build system whether he wants to append $PATH
            # or tuck it at the front: "$PATH;C:\\new\\path", "C:\\new\\path;$PATH"
        #    os.environ["PATH"] = os.path.expandvars(path).encode(sys.getfilesystemencoding())

        proc_env = os.environ.copy()
        proc_env.update(env)
        for k, v in proc_env.iteritems():
            proc_env[k] = os.path.expandvars(v).encode(sys.getfilesystemencoding())
        
        os.environ["PATH"] = "/usr/local/bin:/usr/local/share/python:/Users/raildecom/.rbenv/shims:/Users/raildecom/.rbenv/bin:/Users/raildecom/Scripts:/opt/local/bin:/opt/local/sbin:/usr/local/share/python:/Users/raildecom/.rbenv/shims:/Users/raildecom/.rbenv/bin:/Users/raildecom/Scripts:/opt/local/bin:/opt/local/sbin:/Users/raildecom/.rbenv/shims:/Users/raildecom/.rbenv/bin:/Users/raildecom/Scripts:/opt/local/bin:/opt/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/usr/X11/bin:/usr/local/share/python3"
        self.proc = subprocess.Popen(arg_list, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, startupinfo=startupinfo, env=proc_env, shell=shell)

        if path:
            os.environ["PATH"] = old_path

        if self.proc.stdout:
            thread.start_new_thread(self.read_stdout, ())

        if self.proc.stderr:
            thread.start_new_thread(self.read_stderr, ())

    def kill(self):
        if not self.killed:
            self.killed = True
            self.proc.kill()
            self.listener = None

    def poll(self):
        return self.proc.poll() == None

    def read_stdout(self):
        while True:
            data = os.read(self.proc.stdout.fileno(), 2**15)

            if data != "":
                if self.listener:
                    self.listener.on_data(self, data)
            else:
                self.proc.stdout.close()
                if self.listener:
                    self.listener.on_finished(self)
                break

    def read_stderr(self):
        while True:
            data = os.read(self.proc.stderr.fileno(), 2**15)

            if data != "":
                if self.listener:
                    self.listener.on_data(self, data)
            else:
                self.proc.stderr.close()
                break

class PukeAutoSave(sublime_plugin.EventListener):  

    def on_post_save(self, view):

        if not checkPukeProject():
            return False

        self.window = view.window()
        self.window.run_command('puke', { 'tasks' : ['default']})

    

class PukeTaskCommand(sublime_plugin.WindowCommand, ProcessListener):

    def run (self):
        if not checkPukeProject():
            return False

        self.window.run_command('puke', {'quiet' : True})
        try:
           PukeExec().cmd(['/usr/local/share/python/puke', '--tasks'], self.window.folders().pop(), self.rec_tasks)
        except Exception, msg:
            sublime.error_message(str(msg))
            pass
    
    def rec_tasks(self, data):

        global PukeTasksList
        data.pop(0)
        data = ''.join(data)
        
        data = data.split('\n')
        data.pop(-1)
        self.window.run_command('puke', {'quiet' : True})
        PukeTasksList = data
        self.window.show_quick_panel(data, PukeSelectTask)



class PukeSelectTask:

    def __init__(self, arg):
        global PukeTasksList

        if arg == -1:
            return

        data = PukeTasksList

        task = data[arg].split(':').pop(0)

        sublime.status_message('Running puke %s .....' % task)
        sublime.active_window().run_command('puke', { 'tasks' : [task]})







class PukeCommand(sublime_plugin.WindowCommand, ProcessListener):

    def run(self, tasks = [], options = [], prefix = [], file_regex = "^(...*?):", line_regex = "^...*?:([0-9]*)", working_dir = "",
            encoding = "utf-8", env = {}, quiet = False, kill = False,
            # Catches "path" and "shell"
            **kwargs):
        if not checkPukeProject():
            return False
        
        working_dir = self.window.folders().pop()
        if kill:
            if self.proc:
                self.proc.kill()
                self.proc = None
                self.append_data(None, "[Cancelled]")
            return
        
        

        if not hasattr(self, 'output_view'):
            # Try not to call get_output_panel until the regexes are assigned
            self.output_view = self.window.get_output_panel("exec")

        # Default the to the current files directory if no working directory was given
        if (working_dir == "" and self.window.active_view()
                        and self.window.active_view().file_name() != ""):
            working_dir = os.path.dirname(self.window.active_view().file_name())

        self.output_view.settings().set("result_file_regex", file_regex)
        self.output_view.settings().set("result_line_regex", line_regex)
        self.output_view.settings().set("result_base_dir", working_dir)

        

        current_file = self.window.active_view().file_name()
        current_file_name = os.path.basename(current_file)
        flattened_tasks = ""
        for task in tasks:
            task = string.replace(task, "$file_name", current_file_name)
            task = string.replace(task, "$file", current_file)
            flattened_tasks += task + " "
        flattened_tasks = re.sub(r" $", "", flattened_tasks)

        # Call get_output_panel a second time after assigning the above
        # settings, so that it'll be picked up as a result buffer
        self.window.get_output_panel("exec")

        self.encoding = encoding
        self.quiet = quiet

        self.proc = None

        # Build up the command line
        cmd = []
        cmd += prefix
        cmd += ["/usr/local/share/python/puke"]
        cmd += [flattened_tasks] + options

        self.append_data(None, "> " + " ".join(cmd) + "\n")
        self.window.run_command("show_panel", {"panel": "output.exec"})



        merged_env = env.copy()
        if self.window.active_view():
            user_env = self.window.active_view().settings().get('build_env')
            if user_env:
                merged_env.update(user_env)

        # Change to the working dir, rather than spawning the process with it,
        # so that emitted working dir relative path names make sense
        if working_dir != "":
            os.chdir(working_dir)

        err_type = OSError
        if os.name == "nt":
            err_type = WindowsError

        #kwargs['shell'] = True

        try:
            # Forward kwargs to AsyncProcess
            self.proc = AsyncProcess(cmd, merged_env, self, **kwargs)
        except err_type as e:
            if not self.quiet:
                self.append_data(None, str(e) + "\n")
                self.append_data(None, "[Finished]")

    def is_enabled(self, kill = False):
        if kill:
            return hasattr(self, 'proc') and self.proc and self.proc.poll()
        else:
            return True

    def append_data(self, proc, data):
        if self.quiet:
            return
        if proc != self.proc:
            # a second call to exec has been made before the first one
            # finished, ignore it instead of intermingling the output.
            if proc:
                proc.kill()
            return

        try:
            str = data.decode(self.encoding)
        except:
            str = "[Decode error - output not " + self.encoding + "]"
            proc = None
        
        # Normalize newlines, Sublime Text always uses a single \n separator
        # in memory.
        str = str.replace('\r\n', '\n').replace('\r', '\n')
        str = re.sub('\[(\d+)m', '', str)
        selection_was_at_end = (len(self.output_view.sel()) == 1
            and self.output_view.sel()[0]
                == sublime.Region(self.output_view.size()))
        self.output_view.set_read_only(False)
        edit = self.output_view.begin_edit()
        self.output_view.insert(edit, self.output_view.size(), str)
        if selection_was_at_end:
            self.output_view.show(self.output_view.size())
        self.output_view.end_edit(edit)
        self.output_view.set_read_only(True)

    def finish(self, proc):
        if not self.quiet:
            self.append_data(proc, "[Finished]")
        if proc != self.proc:
            return

        # Set the selection to the start, so that next_result will work as expected
        edit = self.output_view.begin_edit()
        self.output_view.sel().clear()
        self.output_view.sel().add(sublime.Region(0))
        self.output_view.end_edit(edit)

    def on_data(self, proc, data):
        sublime.set_timeout(functools.partial(self.append_data, proc, data), 0)

    def on_finished(self, proc):
        sublime.set_timeout(functools.partial(self.finish, proc), 0)
