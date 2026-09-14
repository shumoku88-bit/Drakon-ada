-- Generated from DRAKON and explicit ada metadata. DO NOT EDIT.
package body Branch with SPARK_Mode => On is
   procedure Absolute_Value (Input : in Number; Result : out Magnitude) is
   begin
        if Input >= 0 then
            Result := Input;
        else
            Result := -Input;
        end if;
   end Absolute_Value;
end Branch;
