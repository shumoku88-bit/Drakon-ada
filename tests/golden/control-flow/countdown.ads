-- Generated from DRAKON and explicit ada metadata. DO NOT EDIT.
package Countdown with SPARK_Mode => On is
   type Number is range 0 .. 10;

   procedure Count_Down (Amount : in Number; Count : out Number)
     with Post => Count = 0, Always_Terminates => True;
end Countdown;
