
# This program is free and subject to the conditions of the MIT license.
# If you care to read that, here's a link:
# http://opensource.org/licenses/MIT

#===================== IMPORTS --- SETUP --- GLOBAL VARS ======================
import os
import sys
import re

#import stuff from boto
from boto.mturk.question import *


class AnswerKey(ValidatingXML, list):
    schema_url = 'http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2005-10-01/AnswerKey.xsd'
    xml_template = '''<?xml version="1.0" encoding="UTF-8"?>
<AnswerKey xmlns="{}">
    {}
</AnswerKey>'''

    def get_as_xml(self):
        items = '\n'.join(item.get_as_xml() for item in self)
        return self.xml_template.format(self.schema_url, items)


class AnswerOption():
    def __init__(self, question_IDs, score):
        self.question_IDs = question_IDs
        self.score = score
        self.template = '''
        <AnswerOption>
        {}
        </AnswerOption>
        '''

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


#================================= __MAIN__ ===================================
def main():
    with open('test.xml', 'w') as test:
        #test.write(parse_question_file('english.questions').get_as_xml())
        test.write(parse_answer_file('english.answers').get_as_xml())

#------------------------------------------------------------------------------
if __name__ == '__main__':
    main()

