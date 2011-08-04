#==========FHICLPY===============================================================================
# AUTHOR: Ryan Putz
# This is a python-based parser which utilizes the PyParsing module by Paul McGuire.
# It is a top-down, recursive descent parser.
#
# IMPLEMENTATION DIFFERENCES:
#    This version of fhicl-py allows for the overriding of prolog entries by non-prolog entries
#    of the same name. This change is in accordance with git commit #69b72b863987c8b52ca781f1823c2c447b887ccf
#    of fhicl-cpp wherein a similar modification was made.
# 
# CURRENT ISSUES: de-generalize pyparsing import
#================================================================================================
import sys, string, re, decimal, ast
import os.path
sys.path.append("/home/putz/fhicl/fhicl/fhicl-py")
sys.path.append("/home/putz/fhicl/fhicl/fhicl-py/orderedDict.py")

#Make this more specific later
from pyparsing import *
from orderedDict import OrderedDict
from decimal import *

#========================================================
#                 CUSTOM EXCEPTIONS
#========================================================
class INVALID_TOKEN(Exception):
   def __init__(self, stmt):
      self.msg = "Invalid token detected, resulting in an empty parameter set: " + stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_KEY(Exception):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_INCLUDE(Exception):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

class PARSE_FAILURE(ParseSyntaxException):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

class ILLEGAL_STATEMENT(Exception):
   def __init__(self, stmt, i):
      self.msg = "Illegal statement found before PROLOG at line " + str(i) + " => " + stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_ASSOCIATION(Exception):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

#========================================================
#           PARSE BEHAVIOR FUNCTIONS/METHODS
#========================================================

#joining two dictionaries (recursive)
def join(A, B):
    if not isinstance(A, dict) or not isinstance(B, dict):
        return A or B
    return dict([(a, join(A.get(a), B.get(a))) for a in set(A.keys()) | set(B.keys())])

#Function for converting string to int
def convertInt(origString, loc, tokens):
   return int(tokens[0])

#Function for converting string to long
def convertLong(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   return long(tokens[0])

#Function for converting string to float
def convertFloat(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   #if representable as an int, do it
   if (int(float(tokens[0])) == float(tokens[0])):
      return int(Decimal(tokens[0]))
   else:
      return float(Decimal(tokens[0]))

#Function for converting string to complex
def convertComplex(tokens):
   cmplx = ast.literal_eval(tokens[0])
   return cmplx
   
#Function for converting string to scientific notation
def convertSci(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   number = str(float(Decimal(tokens[0])))
   number = re.sub(r'([Ee])\+',r'\1',number)
   if int(Decimal(number)) == float(number): 
      number = str(int(Decimal(number)))
   return '%s' % (number,)
   
#Function for converting string to hexadecimal 
def convertHex(origString, loc, tokens):
   return int(tokens[0], 16)

#Function for converting to a list
def convertList(tokens):
   return tokens.asList()

#hname storage:
#Items in this list are left-hand heirarchical names
#that are to be removed from the parameter set after
#being resolved
delItems = []


#========================================================
#                       GRAMMAR
#========================================================
# Leading "NoMatch()" elements indicate what to do if the 
# parser can't match a token once it has committed to a type


#Comments:
#Allows combined grammar to ignore commented lines
comment= oneOf('# //') + ZeroOrMore(Word(r'*')) + LineEnd()
pcomment= Regex(r'\#.*') + LineEnd()
ccomment= Regex(r'//.*') + LineEnd()

#Parameter Set Grammar:
#Separate from prolog grammar so that prolog may be processed independently.
def Syntax():

   #(Bottom)
   # --BOOLEAN--
   true= Word("True")
   false= Word("False")
   bool= true | false

   # --MISC--
   ws= Regex(r'\s*').suppress()
   lparen= Literal("(").suppress()
   rparen= Literal(")").suppress()
   colon= NoMatch().setName("colon") | (ws + ':' + ws)
   local= Regex(r'@local::')
   db= Regex(r'@db::')

   # --NUMBER--
   null= Word('nil')
   infinity= oneOf( 'infinity' '+infinity' '-infinity')
   integer= Word(nums).setParseAction(convertInt)
   #float= MatchFirst(Word(nums, ".") | Word(nums, ".", nums)).setParseAction(convertFloat)
   float= Regex(r'[\d]*[.][\d*]').setParseAction(convertFloat)
   hex= Regex(r"(0x|$)[0-9a-fA-F]+").setParseAction(convertHex)
   sci= Regex(r'[0-9\W]*\.[0-9\W]*[eE][0-9]*').setParseAction(convertSci)
   simple= float | integer
   complex= Combine(lparen + ws + simple + ws + "," + ws + simple + ws + rparen).setParseAction(convertComplex)
   number=  NoMatch().setName("number") | MatchFirst(sci | complex | hex | simple | infinity)
        
   # --STRING--
   uquoted= Word(alphas+'_', alphanums+'_')
   squoted = Regex(r'\'(?:\\\'|[^\'])*\'', re.MULTILINE)
   dquoted = Regex(r'\"(?:\\\"|[^"])*\"', re.MULTILINE)
   string= MatchFirst(dquoted | squoted | uquoted)
   name= NoMatch().setName("name") | uquoted
   dot= Regex(r'[.]') + name
   bracket= Regex(r'\[[\d]\]')
   #Added "Combine" to recognize hname token
   hname= NoMatch().setName("hname") | Combine(name + (bracket|dot) + ZeroOrMore(bracket|dot))
   id= MatchFirst(hname | name).setName("ID")
   ref= NoMatch().setName("reference") | (Combine(local - id) | Combine(db - id))

   # --ATOM|VALUE--
   atom= NoMatch().setName("atom") | MatchFirst(ref | number | string | null | bool).setName("atom")
   #table & seq must be forwarded here so that a definition for value can be created
   table= Forward()
   seq= Forward()
   value= NoMatch().setName("value") | MatchFirst(atom | seq | table).setName("value")

   # --ASSOCIATION-
   association= (id - colon - value)
        
   # --SEQUENCE--
   seq_item= NoMatch().setName("seq_item") | MatchFirst(value | Regex(r',').suppress())
   seq_body= nestedExpr('[', ']', seq_item) 
   #filling in forwarded definition
   seq << seq_body

   # --TABLE--
   table_item= NoMatch().setName("table_item") | MatchFirst(association | Regex(r'\s'))
   table_body= nestedExpr('{', '}', table_item)
   #filling in forwarded definition
   table<< table_body

   # --DOCUMENT--
   doc_body= ZeroOrMore(table_item)
   document= doc_body
   return document
   #(Top)

#Prolog grammar. Contains grammar definitions for start and end tags
def Prolog():
   #(Bottom)
   # --BOOLEAN--
   true= Word('true')
   false= Word('false')
   bool= true | false

   # --NUMBER--
   ws= Regex(r'\s*').suppress()
   lparen= Literal("(").suppress()
   rparen= Literal(")").suppress()
   null= Word('nil')
   infinity= oneOf( 'infinity' '+infinity' '-infinity')
   integer= Word(nums).setParseAction(convertInt)
   #float= MatchFirst(Word(nums, ".") | Word(nums, ".", nums)).setParseAction(convertFloat)
   float= Regex(r'[\d]*[.][\d*]').setParseAction(convertFloat)
   hex= Regex(r"(0x|$)[0-9a-fA-F]+").setParseAction(convertHex)
   sci= Regex(r'[0-9\W]*\.[0-9\W]*[eE][0-9]*').setParseAction(convertSci)
   simple= float | integer
   complex= Combine(lparen + ws + simple + ws + "," + ws + simple + ws + rparen).setParseAction(convertComplex)
   number=  NoMatch().setName("number") | MatchFirst(sci | complex | hex | simple | infinity)

   # --STRING--
   uquoted= Word(alphas+'_', alphanums+'_')
   squoted = Regex(r'\'(?:\\\'|[^\'])*\'', re.MULTILINE)
   dquoted = Regex(r'\"(?:\\\"|[^"])*\"', re.MULTILINE)
   string= MatchFirst(dquoted | squoted | uquoted)
   name= NoMatch().setName("name") | uquoted
   dot= Regex(r'[.]') + name
   bracket= Regex(r'\[[\d]\]')
   #Added "Combine" to recognize hname token
   hname= NoMatch().setName("hname") | Combine(name + (bracket|dot) + ZeroOrMore(bracket|dot))
   id= MatchFirst(hname | name).setName("ID")

   # --MISC--
   colon= NoMatch().setName("colon") | (ws + ':' + ws)
   local= Regex(r'@local::')
   db= Regex(r'@db::')
   ref= NoMatch().setName("reference") | (Combine(local - id) | Combine(db - id))

   # --ATOM|VALUE--
   atom= NoMatch().setName("atom") | MatchFirst(ref | number | string | null | bool).setName("atom")
   #table & seq must be forwarded here so that a definition for value can be created
   table= Forward()
   seq= Forward()
   value= NoMatch().setName("value") | MatchFirst(atom | seq | table).setName("value")

   # --ASSOCIATION-
   association= (id + colon - value)

   # --SEQUENCE--
   seq_item= NoMatch().setName("seq_item") | MatchFirst(value | Regex(r',').suppress())
   seq_body= nestedExpr('[', ']', seq_item)
   #filling in forwarded definition
   seq << seq_body

   # --TABLE--
   table_item= NoMatch().setName("table_item") | MatchFirst(association | Regex(r'\s'))
   table_body= nestedExpr('{', '}', table_item)
   #filling in forwarded definition
   table<< table_body

   # --PROLOG--
   begin= Literal("BEGIN_PROLOG").suppress()
   end= Literal("END_PROLOG").suppress()
   prolog= begin + Optional(OneOrMore(table_item)) + end
   prologs= OneOrMore(prolog)
   return prologs

#========================================================
#                      END GRAMMAR
#========================================================

#========================================================
#                      FUNCTIONS/METHODS
#========================================================

#Is the passed string an include statement?
def isInclude(s):
        exists = s.count("#include") > 0
        if exists:
           BoL = s.index("#include") == 0
           if BoL:
              space = (s.count(" ") >= 1 and s.index(" ") == 8)
              if space:
                 return True
              else:
                 raise INVALID_INCLUDE(s + " is not a valid include statement.")
           else:
              return False
        else:
           return False

#Is the passed string a comment?
def isComment(s):
   if not(isInclude(s)):
      if (s.count("#") > 0 or s.count(r'//') > 0):
         if s.count("#") > 0:
            if s.index("#") == 0:
               return True
            else:
               return False
         elif s.count(r'//') > 0:
            if s.index(r'//') == 0:
               return True
            else:
               return False
      else:
         return False
   else:
      return False     

#Is the passed string a reference?
def isRef(s):
   return str(s).count("::") > 0 and str(s).count("@") > 0

#Is the passed string an hname?
def isHName(s):
        return (str(s).count(".") > 0 or (str(s).count("[") > 0 and str(s).count("[") == str(s).count("]")))

#Checks to see if a document (string) is considered "empty"
#A document is considered "empty" if it contains only comments or only (a) prolog(s).
def isEmptyDoc(s):
        content = s.splitlines(1)
        #if there's nothing in s
        if len(content) == 0:
           return True
        else:
           for line in content:
              #broken!
              if (not(isComment(line)) and line != "" and line != "\n"):
                 return False
        return True

#Function which looks for matching pairs of single or double quotes
def isString(s):
   s = str(s)
   if s.count("'") == 2:
      if s.find("'") == 0 and s.rfind("'") == len(s) - 1:
         return True
   elif s.count('"') == 2:
      if s.find('"') == 0 and s.rfind('"') == len(s) - 1:
         return True
   else:
      return False

#Reads External file and returns the contents
def handleInclude(s):
   name = s.split('"')
   try:
      name = name[1]
      file = open(name)
      fileContents = file.read()
      return fileContents
   except:
      raise INVALID_INCLUDE(s + " is not a valid include statement.")
              
#Function to handle includes before grammar parsing begins      
def checkIncludes(s):
        content = s.splitlines(1)
        pcontent = str("")
        i = 0
        while i < len(content):
           #Is the line an include?
           if isInclude(content[i]):
              fileContents = handleInclude(content[i])
              if fileContents != None:
                 if fileContents.count("#include") > 0:
                    fileContents = handleInclude(fileContents)
                 pcontent += fileContents
           #Otherwise just add it to the parsed content
           else:
              #Either raise an error if we're picky about include syntax
              #OR treat it as a comment

              #raise INVALID_INCLUDE("Syntax error on line " + str(i))
              pcontent += content[i]
           i += 1
        #return the parsed content
        return pcontent
#Function that determines which type of indexing is being used in an hname.
#The two options are DOT(".") index or BRACKET("[]") index.
#The decision is made based on existence and location within a string
def detIndType(s):
   s = str(s)
   b = s.find("[")
   d = s.find(".")
   if b == -1 and d > -1:
      return "."
   if d == -1 and b > -1:
      return "["
   if b == -1 and d == -1:
      #raise KeyError(s + " invalid hname indexing")
      return ""
   elif ( d <= b):
      return "."
   elif ( b <= d):
      return "["

#Utility function for stripping off the closing bracket in bracket notation
def stripCloseB(s):
   s = str(s).split("]", 1)
   s = s[0] + s[1]
   return s

#Function that handles look-up of hname references
def handleRHname(s, d):
   indexChar = detIndType(s)
   if indexChar != "":
      if indexChar == "[":
         s = stripCloseB(s)
      s = s.split(indexChar, 1)
      key = s[0]
      rest = s[1]
      if type(d) is list and len(d)-1 > int(key):
         return handleRHname(rest, d[int(key)])
      elif key in d:
         return handleRHname(rest, d[key])
      else:
         raise KeyError(key + " in handleRHname(inner)")
   elif s in d:
      return d[s]
   else:
      raise KeyError(s + " in handleRHname(outer)")

#Function that handles overrides using hnames
def handleLHname(s, d, v):
   indexChar = detIndType(s)
   if indexChar != "":
      if indexChar == "[":
         s = stripCloseB(s)
      s = s.split(indexChar, 1)
      key = s[0]
      rest = s[1]
      return handleRHname(rest, d[key])
   else:
      if type(d) is list:
         index = int(s)
         if index > (len(d) - 1):
            d.append(v)
         else:
            d[int(s)] = v
         return d
      else:
         #change to d[s] = v to change behavior
         #move "return d" from 2 lines up to outside if/else

         #problem occurs here!!!
         #Fixed - ish
         return dict(zip(list(s), list(str(v))))

#This function steps through the assembled parameter set
#and handles resolution of references and overrides.
def postParse(d, p):
   #Iterate through the dictionary
   for k, v in d.iteritems():
      #Recursive conversion of OrderedDicts to dicts
      if type(v) is OrderedDict:
         d[k] = postParse(dict(v), p)
      #Found a reference
      if isRef(v):
         key = v.split("::")[1]
         indChar = detIndType(key)
         #if it's an HName
         #Can probably change this to use "IsHName(s)"
         if indChar != "":
            #If it's a brace index, strip off the closing brace
            if indChar == "[":
               key = stripCloseB(key)
            #split at the indexing character
            testKey = key.split(indChar, 1)[0]
            #check to see if the leading name is in the document dictionary
            if testKey in d:
               #if so, recursively handle the hname
               v = handleRHname(key, d)
               d[k] = handleRHname(key, d)
            #else check to see if the key is in the prolog dictionary
            elif testKey in p:
               #if so, recursively handle the hname
               d[k] = handleRHname(key, p)
               v = handleRHname(key, p)
            else:
               #Otherwise, error out
               raise KeyError("In postParse: " + testKey)
         #If it's not an hname
         #check to see if the name exists in d
         elif key in d:
            d[k] = d[key]
         #else check to see if the name exists in p
         elif key in p:
            d[k] = p[key]
         else:
            raise KeyError("In postParse: " + key)
      #If it's an hname
      if isHName(k):
         #determine which type of indexing is being used next
         splitChar = detIndType(k)
         newKey = k
         #If there is a type of index being used 
         if splitChar != "":
            #If it's bracket indexing, strip of the closing bracket
            if splitChar == "[":
               newKey = stripCloseB(k)
            #Split on the splitChar
            newKey = newKey.split(splitChar, 1)
            #Two pieces: chunk before split char => newKey
            #            chunk after split char => rest
            rest = newKey[1]
            newKey = newKey[0]
            #If the newKey is in the PSet
            if newKey in d:
               #Handle hname override
               d[newKey] = handleLHname(rest, d[newKey], v)
            #Else if newKey is in the Prolog
            elif newKey in p:
               #Handle hname override 
               
               #Change 'd' to 'p' to change behavior of test case: adv_ref_pass.fcl
               #Making this change will affect the output as such:
               #Before change: { a:6 }
               #After change: { a:6 tab1:{ a:7 } }
               d[newKey] = handleLHname(rest, p[newKey], v)
         #Breaks when there is no prolog
         if p != {}:
            #Add an hname key to be deleted from the finished product
            delItems.append(k)
   #Clean up resolved overrides
   for k in delItems: 
      del d[k]
   return d

#Function that checks the input string for illegal statements before prologs
def orderCheck(s):
   content = s.splitlines();
   i = 0
   while i < len(content) - 1: 
      if not(isComment(content[i])) and content.count("BEGIN_PROLOG") > 0:
         j = content.index("BEGIN_PROLOG")
         if j > i:
            raise ILLEGAL_STATEMENT(content[i], i)
      i += 1
   return True

#Construction of a parameter set. Used for both the prolog and document body
def buildPSet(toks):
   #We're creating a dictionary, so we'll need keys and values to map to them:
   keys = []
   vals = []

   #Step through the parse tree (toks)
   while len(toks) > 0:
      #Checks to ensure that there are tokens to process and that each line is a valid association
      #This check works because all non-association elements have been removed by this point.
      #Could potentially dump this check all together as anything that doesn't have a ":" in it at this point is invalid
      #NO! Necessary for dual-useage in assembling prolog
      if len(toks) > 1 and str(toks[1]) == (":"):
         keys.append(toks.pop(0)) #pop the "key" token and append it to the list of keys
         toks.pop(0) #dumping the ":"
         #Still have tokens left?
         if len(toks) > 0:
            #If it's not a quoted string
            if not isString(toks[0]):
               #Reference checking/handling
               if str(toks[0]).count("@") > 0 and str(toks[0]).index("@") == 0:
                  vals.append(toks.pop(0))
               #Sequence/Table checking/handling
               #In the parse tree of tokens, fhicl sequences and tables are both denoted by brackets ("[]")
               #Tables, however, contain associations, so we can make a distinction based on if the body contains (":")
               elif str(toks[0]).count("[") > 0 and str(toks[0]).count("[") == str(toks[0]).count("]"):
                  #In the parse tree of tokens, fhicl sequences and tables are both denoted by brackets ("[]")
                  #Tables, however, contain associations, so we can make a distinction based on if the body contains (":")
                  #These 4 lines of code handle the case of "I have a sequence of tables"
                  #I.E. seq:[ { a:1 b:2 }, { c:3 d:4 } ]
                  #Wherein the parse tree treats everything as lists of tokens until we assemble them here.
                  #So we can't just blindly check for (":"), and we have to ensure that we're not calling it a table
                  #if it's really a sequence of tables.
                  secBrack = -1
                  if str(toks[0]).count("[") > 1:
                     strg = str(toks[0]).split("[", 1)[1]
                     secBrack = strg.index("[")
                  #Table
                  if str(toks[0]).count(":") > 0 and (secBrack == -1 or str(toks[0]).index(":") < secBrack):
                     vals.append(buildPSet(toks.pop(0)))
                  else:
                     #Manually assemble list, checking to see if each element is a non-table value or a table body
                     val = []
                     for item in toks[0]:
                        if str(item).count(":") > 0:
                           val.append(buildPSet(item))
                        else:
                           val.append(item)
                     vals.append(val)
                     #done with that token, trash it.
                     toks.pop(0) 
               #Otherwise we have an unquoted string/numeric
               else:
                  vals.append(toks.pop(0))
            #Otherwise it's a quoted string
            else:
               vals.append(toks.pop(0))
         #Otherwise the association is malformed
         else:
            raise INVALID_ASSOCIATION("Invalid Association @ " + str(toks) + "; Valid syntax => name : value")
      #Otherwise it's a BEGIN/END token
      else:
         vals.append(toks.pop(0))
   return OrderedDict(zip(keys, vals))    

#Takes a string, waves its wand, and out comes a complete parameter set.
def parse(s):
        try:
           prologs = []
           doc = Syntax()
           pro = Prolog()

           #ignoring comments
           doc.ignore(ccomment)
           doc.ignore(pcomment)
           #doc.ignore(comment)
           pro.ignore(ccomment)
           pro.ignore(pcomment)

           content = str("")
           isEmpty = False
           #check for empty doc/only comments
           if isEmptyDoc(s):
              #If the document is empty, or just has comments/empty lines
              #Return an empty dictionary
              return dict()
           elif orderCheck(s):  
              #includes checking
              if s.count("#include") > 0:
                 s = checkIncludes(s)
              #handle prolog(s)
              if s.count("BEGIN_PROLOG") > 0:
                 prologStr = s[:s.rfind("END_PROLOG")+10]
                 s = s[s.rfind("END_PROLOG")+10:len(s)]
                 prologs = pro.parseString(prologStr)
                 prologs = buildPSet(prologs)
                 prologs = postParse(prologs, {})
              #parse contents of file
              docStr = doc.parseString(s)
              #convert over to proper dictionary
              docStr = buildPSet(docStr)  
              #resolving references and hnames
              docStr = postParse(docStr, prologs)
              #Sanity check
              if docStr == {} and not(isEmptyDoc(s)):
                 raise INVALID_TOKEN(str(docStr))
              else:
                 return dict(docStr)
           else:
              raise ILLEGAL_STATEMENT(str(docStr))
        #Error handling
        except KeyError as e:
           print ("KEY_ERROR: " + "({0})".format(e))
        except INVALID_TOKEN as e:
           print ("INVALID_TOKEN: " + "({0})".format(e))
        except IOError as e:
           print ("IO_ERROR: " + "({0})".format(e))
        except ILLEGAL_STATEMENT as e:
           print ("ILLEGAL_STATEMENT: " + "({0})".format(e))
        except INVALID_INCLUDE as e:
           print ("INVALID_INCLUDE: " + "({0})".format(e))
        except INVALID_ASSOCIATION as e:
           print ("INVALID_ASSOCIATION: " + "({0})".format(e))
        except ParseBaseException as e:
           print ("PARSE_EXCEPTION: " + "({0})".format(e))

#Default setup
if __name__ == '__main__':
        contents = sys.stdin.read()
        d= parse(contents)
        print d
