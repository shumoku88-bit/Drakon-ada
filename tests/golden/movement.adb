-- Generated from DRAKON and explicit ada metadata. DO NOT EDIT.
package body Movement with SPARK_Mode => On is
   procedure Balanced_Movement (Amount : in Positive_Amount; Source : out Quantity; Destination : out Quantity) is
   begin
        Source := -Amount;
        Destination := Amount;
   end Balanced_Movement;
end Movement;
