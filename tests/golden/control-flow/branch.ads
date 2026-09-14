-- Generated from DRAKON and explicit ada metadata. DO NOT EDIT.
package Branch with SPARK_Mode => On is
   type Number is range -10 .. 10;
   subtype Magnitude is Number range 0 .. 10;

   procedure Absolute_Value (Input : in Number; Result : out Magnitude)
     with Post => (Input >= 0 and then Result = Input) or else (Input < 0 and then Result = -Input);
end Branch;
