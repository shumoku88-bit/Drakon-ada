-- Generated from DRAKON and explicit ada metadata. DO NOT EDIT.
package body Countdown with SPARK_Mode => On is
   procedure Count_Down (Amount : in Number; Count : out Number) is
   begin
        Count := Amount;
        loop
            if Count > 0 then
                null;
            else
                exit;
            end if;
            pragma Loop_Invariant (Count > 0 and then Count <= Amount);
            pragma Loop_Variant (Decreases => Count);
            Count := Count - 1;
        end loop;
   end Count_Down;
end Countdown;
