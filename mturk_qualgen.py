'''
Mturk QualGen.

This script makes it easy to generate XML for new qualification types to
be added to Amazon MTurk.

Significantly revised (and simplified) by Ilia Kurenkov in April 2015.
License:
http://opensource.org/licenses/MIT
'''

# ==================== IMPORTS  ======================
import os
import re
from collections import namedtuple
from xml.dom import minidom
from argparse import ArgumentParser


# Read this function to understand what the script does when it's run.
def main():
    '''Main driver function that gets excecuted if you run
    "python mturk_manager.py" from command line.
    Uses argparser for command line arguments.
    Run "mturk_manager.py -h" for details.
    '''
    # Set up command-line option parser
    program_description = ('This program generates qualification test XML '
                           'that can be seng to MTurk.')
    dir_help = ('This argument specifies the folder from which to read '
                'test properties and questions.'
                'By default will look for an "example" folder.')
    arg_parser = ArgumentParser(description=program_description)
    arg_parser.add_argument('testdir',
                            help=dir_help,
                            nargs='?',
                            default='example')
    cmd_arg = arg_parser.parse_args()

    if cmd_arg is 'example':
        print('Warning! You did not specify a target directory. Using "example".')

    # We start by loading a properties file. Currently only the "description"
    # field is used.
    properties_f_name = find_file('properties', cmd_arg.testdir)
    properties = read_settings_file(properties_f_name)

    # load question and answer src file and parse it
    question_src = find_file('questions', cmd_arg.testdir)
    processed_qs = create_namedtuples(parse_question_file(question_src))

    # Generating and writing XML
    # first, we should set up a filename to use for writind
    testname = os.path.basename(cmd_arg.testdir.rstrip('/'))

    question_xml = build_question_xml(processed_qs, properties['description'])
    question_fname = testname + '-questions.xml'
    generate_pretty_xml(question_xml, os.path.join(cmd_arg.testdir, question_fname))

    answers_xml = build_answerkey_xml(processed_qs)
    answerkey_fname = testname + '-answerkey.xml'
    generate_pretty_xml(answers_xml, os.path.join(cmd_arg.testdir, answerkey_fname))


def find_file(f_type, folder):
    '''Given a file type (basically an extension) and a folder in which to
    search for this file type either returns a path to one file with the
    correct extension (should be same as f_type argument) or lets user know
    that it cannot find any such file and halts the program.
    '''
    # make a list of files that fit
    candidates = [f for f in os.listdir(folder)
                  if f.endswith(f_type)]
    # make sure we actually found at least one file
    # if this is not the case, print NO_FILE_ERROR and halt
    NO_FILE_ERROR = ('No "{file_type}" files found. '
                     'Cannot proceed without them')
    assert len(candidates) > 0, NO_FILE_ERROR.format(file_type=f_type)
    # if more than one file found, just alert the user about this
    # and let them know which file we are using
    if len(candidates) > 1:
        MULTIPLE_FILE_WARNING = ('More than one "{file_type}" file found. '
                                 'Using this one: {first_one}')
        print(MULTIPLE_FILE_WARNING.format(file_type=f_type,
                                           first_one=candidates[0]))
    # return usable file path
    return os.path.join(folder, candidates[0])


def read_settings_file(f_path):
    '''Function for reading in properties files.
    Given a file path returns a dictionary of (key, value) pairs read from
    the file found at the path.
    Ignores comments and empty lines.
    '''
    # defined filtering function
    not_comment_empty = lambda line: not line.startswith('#') and line.strip()
    # open file for reading
    with open(f_path) as settings_file:
        # filter out comments and empty lines
        lines_to_read = filter(not_comment_empty, settings_file)
        # split lines across "=" character
        split_lines = (line.split('=') for line in lines_to_read)
        # remove all trailing whitespace
        no_trailing_whtspc = (map(str.strip, pair) for pair in split_lines)
        # convert to dictionary and return
        return dict(no_trailing_whtspc)


def parse_question_file(question_path):
    '''Given path to file with all the questions reads both questions and answers
    from it into a nested dictionary.
    '''
    with open(question_path, 'rU') as q_file:
        # read in the whole file
        file_str = q_file.read()

    # Define and compile regexes for searching through question file.
    question_search_str = ('Question (?P<type>\w*)\s*?'
                           '(?P<content>.*?)'
                           '(?P<answers>Answer.*?)'
                           'Score (?P<score>\d+?)')
    qu_rgx = re.compile(question_search_str, flags=re.DOTALL)

    answers_search_str = ('Answer(?P<text>.*?)\s*?'
                          'correct (?P<correct>\d*)')
    a_rgx = re.compile(answers_search_str, flags=re.DOTALL)

    # filter out all comments
    no_comments = re.sub('#.*', '', file_str)

    # extract question blocks
    parsed_questions = search_add_ids(no_comments, qu_rgx, 'q')

    for q_dict in parsed_questions:
        q_dict['content'] = q_dict['content'].strip()
        q_dict['answers'] = search_add_ids(q_dict['answers'], a_rgx, 'a')

    return parsed_questions


def search_add_ids(string, rgx, suffix):
    '''Takes a string, a regular expression and a suffix.
    Uses regular expression to search through string and creates a list of dictionaries
    from what it finds. To each dictionary in this list an "id" key is added.
    '''
    # turn all matches to passed rgx into dictionaries where keys are taken
    # from pattern names defined in rgx
    found_dicts = [match.groupdict() for match in rgx.finditer(string)]
    for n, match_dict in enumerate(found_dicts):
        match_dict['id'] = suffix + str(n + 1)
    return found_dicts


def create_namedtuples(parsed_questions):
    Question = namedtuple('Question', 'id type content score answers')
    Answer = namedtuple('Answer', 'id text correct')
    for pq in parsed_questions:
        pq['answers'] = [Answer(**ans) for ans in pq['answers']]

    return [Question(**q) for q in parsed_questions]


def build_question_xml(data, description):
    # some boilerplate needed to start creating the document.
    xmlns = ("http://mechanicalturk.amazonaws.com/"
             "AWSMechanicalTurkDataSchemas/2005-10-01/QuestionForm.xsd")
    impl = minidom.getDOMImplementation()

    doc = impl.createDocument(None, 'QuestionForm', None)
    root = doc.documentElement
    root.setAttribute('xmlns', xmlns)

    overview = sub_element(doc, root, 'Overview')
    sub_element(doc, overview, 'Title', text=description)

    for ques in data:
        q_el = sub_element(doc, root, 'Question')
        sub_element(doc, q_el, 'QuestionIdentifier', ques.id)
        sub_element(doc, q_el, 'IsRequired', 'true')
        q_content = sub_element(doc, q_el, 'QuestionContent')
        add_cdata_element(doc, q_content, 'Text', ques.content)

        ans_spec = sub_element(doc, q_el, 'AnswerSpecification')
        selection_ans = sub_element(doc, ans_spec, 'SelectionAnswer')
        sub_element(doc, selection_ans, 'StyleSuggestion', ques.type)
        selections = sub_element(doc, selection_ans, 'Selections')
        for a in ques.answers:
            select = sub_element(doc, selections, 'Selection')
            sub_element(doc, select, 'SelectionIdentifier', a.id)
            add_cdata_element(doc, select, 'Text', a.text.strip())

    return doc


def build_answerkey_xml(data):
    # some boilerplate needed to start creating the document.
    xmlns = ("http://mechanicalturk.amazonaws.com/"
             "AWSMechanicalTurkDataSchemas/2005-10-01/AnswerKey.xsd")
    impl = minidom.getDOMImplementation()
    doc = impl.createDocument(None, 'AnswerKey', None)
    root = doc.documentElement
    root.setAttribute('xmlns', xmlns)
    for ques in data:
        q_el = sub_element(doc, root, 'Question')
        sub_element(doc, q_el, 'QuestionIdentifier', ques.id)
        for a in ques.answers:
            if not int(a.correct) > 0:
                continue
            option = sub_element(doc, q_el, 'AnswerOption')
            sub_element(doc, option, 'SelectionIdentifier', text=a.id)
            sub_element(doc, option, 'AnswerScore', ques.score)

    return doc


def sub_element(doc, parent, tag, text=None):
    '''The workhorse of xml building. Creates a new element tagged with `tag`,
    optionally adds text to it, then attaches it to `parent`. The new element is
    returned.
    '''
    new_el = doc.createElement(tag)
    if text is not None:
        txt_node = doc.createTextNode(text)
        new_el.appendChild(txt_node)

    return parent.appendChild(new_el)


def add_cdata_element(doc, parent, tag, text):
    '''CDATA needed slightly different treatment, but in essence this does the
    same as `sub_element`.
    '''
    data_el = sub_element(doc, parent, tag)
    cdata = doc.createCDATASection(text)
    return data_el.appendChild(cdata)


def generate_pretty_xml(xml, f_name):
    # The options passed to writexml ensure the output is readable by a human.
    # For some weird reason CDATA entries don't obey the indentation rules.
    xml.writexml(open(f_name, 'w'), addindent='  ', newl='\n', encoding='UTF-8')


# -----------------------------------------------------------------------------
if __name__ == '__main__':
    main()
