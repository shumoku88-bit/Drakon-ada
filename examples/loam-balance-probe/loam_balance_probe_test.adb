with Ada.Text_IO;
with Loam_Balance_Admission;

procedure Loam_Balance_Probe_Test is
   use type Loam_Balance_Admission.Quantity;
   Total    : Loam_Balance_Admission.Quantity;
   Accepted : Boolean;
   Expected : Boolean;
   Count    : Natural := 0;
begin
   for First in Loam_Balance_Admission.Change_Quantity loop
      for Second in Loam_Balance_Admission.Change_Quantity loop
         for Third in Loam_Balance_Admission.Change_Quantity loop
            Loam_Balance_Admission.Admit_Three_Changes
              (First, Second, Third, Total, Accepted);
            if Total /= First + Second + Third then
               raise Program_Error with "balance total mismatch";
            end if;
            Expected := Total = 0;
            if Accepted /= Expected then
               raise Program_Error with "balance admission mismatch";
            end if;
            Count := Count + 1;
         end loop;
      end loop;
   end loop;
   if Count /= 9_261 then
      raise Program_Error with "unexpected test-domain cardinality";
   end if;
   Ada.Text_IO.Put_Line
     ("PASS: LOAM balance admission witness, all 9,261 bounded triples");
end Loam_Balance_Probe_Test;
