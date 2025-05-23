import multiprocessing
import traceback

from interfaz import (
    select_token_slot,
    select_library_file,
    get_pin_from_user,
    select_certificate,
)

def _ui_worker(func_name, queue, args):
    """Executes the requested GUI function and puts the result in the queue.

    Parameters
    ----------
    func_name : str
        Name of the UI helper to execute.
    queue : multiprocessing.Queue
        Queue used to return the result to the parent process.
    args : tuple
        Positional arguments to pass to the UI helper.
    """
    try:
        if func_name == "select_token_slot":
            token_info_list, mode = args
            result_container = []
            select_token_slot(token_info_list, result_container, mode)
            queue.put(result_container[0] if result_container else None)
        elif func_name == "select_certificate":
            certificates, mode = args
            result_container = []
            select_certificate(certificates, result_container, mode)
            queue.put(result_container[0] if result_container else None)
        elif func_name == "select_library_file":
            queue.put(select_library_file())
        elif func_name == "get_pin_from_user":
            (mode,) = args
            queue.put(get_pin_from_user(mode))
        else:
            queue.put(None)
    except Exception:
        traceback.print_exc()
        queue.put(None)


def run_ui(func_name: str, args: tuple = ()):
    """Runs a small Tkinter UI helper in a separate process and returns its result.

    All UI helpers are executed in a separate process to avoid blocking the Flask
    thread and to prevent Tcl/Tk crashes that can occur when Tkinter is used
    from a non-main thread on some platforms.
    """
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=_ui_worker, args=(func_name, q, args))
    p.start()
    p.join()
    try:
        return q.get_nowait()
    except Exception:
        return None 