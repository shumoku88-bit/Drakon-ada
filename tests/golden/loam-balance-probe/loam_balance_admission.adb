-- Generated from DRAKON and explicit ada metadata. DO NOT EDIT.
package body Loam_Balance_Admission with SPARK_Mode => On is
   procedure Admit_Three_Changes (First : in Change_Quantity; Second : in Change_Quantity; Third : in Change_Quantity; Total : out Quantity; Accepted : out Boolean) is
   begin
        Total := First + Second + Third;
        if Total = 0 then
            Accepted := True;
        else
            Accepted := False;
        end if;
   end Admit_Three_Changes;
end Loam_Balance_Admission;
