
#To-do:
    #turn English test into text file?
# http://opensource.org/licenses/MIT

#===================== IMPORTS --- SETUP --- GLOBAL VARS ======================
import os
import sys
import re

#import stuff from boto
from boto.mturk.question import *
from boto.mturk.connection import MTurkConnection
from argparse import ArgumentParser

#================================= __MAIN__ ===================================


def main():
    # define some strings for ArgParser
    progr_descr = 'This program loads native qualification tests into MTurk.'
    lang_help = 'This specifies the folder from which to read questions and answers.'
    account_help = 'This specifies the folder from which to read credential information.'
# set up argument parser
    arg_parser = ArgumentParser(description=progr_descr)
    arg_parser.add_argument('language', help=lang_help)
    arg_parser.add_argument('account', help=account_help)
    cmd_arg = arg_parser.parse_args()

# set up language directory
    root = os.getcwd()
    if cmd_arg.language not in os.listdir(root):
        raise MissingFolderException(cmd_arg.language)

    lang_root = os.path.join(root, cmd_arg.language)

# load properties file
    properties_f_name = find_file('properties', lang_root)
    properties = process_properties_file(properties_f_name)

# load question and answer src files
    question_src = find_file('questions', lang_root)
    question_xml = parse_question_file(question_src)
    answer_src = find_file('answers', lang_root)
    answer_xml = parse_answer_file(answer_src)

    print question_xml
# set up a connection.
#     connection = create_mturk_connection(os.path.join(root, cmd_arg.account))

# # create qualification test
#     connection.create_qualification_type(name=properties['name'],
#                                          description=properties['description'],
#                                          test=question_xml,
#                                          answer_key=answer_xml,
#                                          status='Active',
#                                          keywords=properties['keywords'],
#                                          retry_delay=properties['retrydelayinseconds'],
#                                          test_duration=properties['testdurationinseconds'])


class AnswerKey(ValidatingXML, list):
    schema_url = ('http://mechanicalturk.amazonaws.com/'
        'AWSMechanicalTurkDataSchemas/2005-10-01/AnswerKey.xsd')
    xml_template = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<AnswerKey xmlns="{schema_url}">\n'
        '{answers}\n'
        '</AnswerKey>\n')

    def get_as_xml(self):
        items = '\n'.join(item.get_as_xml() for item in self)
        return self.xml_template.format(schema_url=self.schema_url, 
            answers=items)


class AnswerOption():
    def __init__(self, question_IDs, score):
        self.question_IDs = question_IDs
        self.score = score
        self.template = ('<AnswerOption>'
            '{}\n'
            '</AnswerOption>\n')

    def get_as_xml(self):
        IDs = [SimpleField('SelectionIdentifier', ID)
               for ID in self.question_IDs]
        fields = IDs + [SimpleField('AnswerScore', self.score)]
        return self.template.format('\n'.join(f.get_as_xml()
                                              for f in fields))


class QuestionAnswer(Question):
    template = '<Question>{}\n{}</Question>'

    def __init__(self, identifier, options):
        self.identifier = SimpleField('QuestionIdentifier', identifier)
        #self.answer_options = [opt.get_as_xml() for opt in options]
        self.answer_options = options

    def get_as_xml(self):
        return self.template.format(self.identifier.get_as_xml(),
                                    self.answer_options.get_as_xml())


def parse_answer_file(file_name):
    q_rgx = re.compile('Question (.*)')
    score_rgx = re.compile('Score (.*)')
    ans_rgx = re.compile('(Answer.+?)(?=Score)', flags=re.DOTALL)
    a_rgx = re.compile('Answer (.+)')
    with open(file_name, 'rU') as ans_file:
        ans_file_str = ans_file.read()
        questions = q_rgx.findall(ans_file_str)
        scores = score_rgx.findall(ans_file_str)
        answers = ans_rgx.findall(ans_file_str)
        assert len(questions) == len(answers) == len(scores)
    question_list = []
    for indx in xrange(len(questions)):
        q_answers = a_rgx.findall(answers[indx])
        answer_opts = AnswerOption(q_answers, scores[indx])
        question_list.append(QuestionAnswer(questions[indx], answer_opts))
    return AnswerKey(question_list)


def parse_question_file(file_name):
    q_rgx = re.compile('Question (\d+) (.+)\s*(.+)')
    a_rgx = re.compile('Answer (.+)\s*(.+)')
    ans_rgx = re.compile('(Answer.+?)(?=Question|END)', flags=re.DOTALL)
    with open(file_name, 'rU') as q_file:
        q_file_str = q_file.read()
        questions = q_rgx.findall(q_file_str)
        answers = ans_rgx.findall(q_file_str)
        assert len(questions) == len(answers)
    question_list = []
    for indx in xrange(len(questions)):
        q_id = questions[indx][0]
        q_type = questions[indx][1]

        q_content = QuestionContent()
        q_content.append_field('Text', questions[indx][2])

        q_answers = a_rgx.findall(answers[indx])
        selection_ans = SelectionAnswer(
            selections=[(x[1], x[0]) for x in q_answers],
            style=q_type)
        question_list.append(Question(q_id,
                                      q_content,
                                      AnswerSpecification(selection_ans),
                                      is_required=True))
    return QuestionForm(question_list)


def find_file(f_type, folder):
    NO_FILE_ERROR = 'No "{}" files found. Cannot proceed without them'
    MULTIPLE_FILE_WARNING = 'More than one "{}" file found. Using this one: {}'
    candidates = [f for f in os.listdir(folder)
                  if f.endswith(f_type)]
    assert len(candidates) > 0, NO_FILE_ERROR.format(f_type)
    if len(candidates) > 1:
        print MULTIPLE_FILE_WARNING.format(f_type, candidates[0])
    return candidates[0]


def process_key_file(f_name):
    with open(f_name, 'rU') as File:
        return dict((line.strip().split('=') for line in File))


def process_properties_file(f_name):
    start = {
        'retrydelayinseconds': '15',
        'testdurationinseconds':  '900'
    }
    with open(f_name, 'rU') as File:
        from_file = dict((line.strip().split('=')
                          for line in File
                          if (bool(line.strip()) and line[0] != '#')))
    start.update(from_file)
    return start


class MissingFolderException(Exception):
    MESSAGE = '''Unable to find the folder "{}".
Please specify a valid folder name.
It's case sensitive.'''

    def __init__(self, folder):
        self.folder = folder

    def __str__(self):
        return self.MESSAGE.format(self.folder)



#================================= __MAIN__ ===================================

def main():
# set up argument parser
    arg_parser = ArgumentParser(description='This program loads native qualification tests into MTurk.')
    arg_parser.add_argument('language',
                            help='This specifies the folder from which to read questions and answers.')
    arg_parser.add_argument('account',
                            help='This specifies the folder from which to read credential information.')
    cmd_arg = arg_parser.parse_args()

# set up language directory
    root = os.getcwd()
    if cmd_arg.language not in os.listdir(root):
        raise Exception('Unable to find the folder with question and answer files. Please make sure to s')
        lang_root = os.path.join(root, cmd_arg.language)
    else:
        raise kkk

# load properties file
    properties_f_name = find_file('properties', lang_root)
    properties = process_properties_file(properties_f_name)

# load question and answer src files
    question_src = find_file('questions', lang_root)
    question_xml = parse_question_file(question_src)
    answer_src = find_file('answers', lang_root)
    answer_xml = parse_answer_file(answer_src)

# load secure keys
    key_f_name = os.path.join(root, cmd_arg.account, 'rootkey.csv')
    keys = process_key_file(key_f_name)
# create connection
    connection = MTurkConnection(aws_access_key_id=keys['AWSAccessKeyId'],
                                 aws_secret_access_key=keys['AWSSecretKey'])

# this is just development stuff
    #with open('test.xml', 'w') as test:
        #test.write(parse_question_file('english.questions').get_as_xml())
        #test.write(parse_answer_file('english.answers').get_as_xml())

    connection.create_qualification_type(name=properties['name'],
                                         description=properties['description'],
                                         test=question_xml,
                                         answer_key=answer_xml,
                                         status='Active',
                                         keywords=properties['keywords'],
                                         retry_delay=properties['retrydelayinseconds'],
                                         test_duration=properties['testdurationinseconds'])

#------------------------------------------------------------------------------
if __name__ == '__main__':
    main()

