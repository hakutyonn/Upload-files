import sys,tempfile,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mamori_guardian import scan,compare
class Tests(unittest.TestCase):
 def test_changed_and_new(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);a=p/"a.txt";a.write_text("old");before,_,_=scan([p]);a.write_text("new");(p/"b.txt").write_text("new");after,_,_=scan([p]);events,active=compare(before,after,{})
   self.assertEqual({x[0] for x in events},{"FILE_CHANGED","FILE_NEW"});self.assertEqual(len(active),2)
 def test_deleted(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);a=p/"a.txt";a.write_text("x");before,_,_=scan([p]);a.unlink();after,_,_=scan([p]);events,_=compare(before,after,{})
   self.assertIn("FILE_MISSING",{x[0] for x in events})
 def test_no_duplicate(self):
  b={"x":{"sha256":"a","size":1}};c={"x":{"sha256":"b","size":1}};ev,active=compare(b,c,{})
  ev2,_=compare(b,c,active);self.assertEqual(len(ev),1);self.assertEqual(len(ev2),0)
 def test_reverted(self):
  b={"x":{"sha256":"a","size":1}};ev,active=compare(b,b,{"x":"b"})
  self.assertEqual(ev[0][0],"FILE_CHANGE_REVERTED");self.assertEqual(active,{})
 def test_safe_defaults(self):
  cfg=json.loads((Path(__file__).resolve().parents[1]/"config/config.json").read_text())
  self.assertFalse(cfg["auto_remediation"]);self.assertEqual(cfg["dashboard_port"],8765)
if __name__=="__main__":unittest.main()
